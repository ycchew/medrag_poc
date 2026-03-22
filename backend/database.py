"""
Database connection pool and utilities for the Clinic AI Assistant.
"""

import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

from config import DATABASE_CONFIG, DATABASE_URL


class DBPool:
    """Database connection pool."""

    _pool = None

    @classmethod
    def get_pool(cls):
        """Get or create the connection pool."""
        if cls._pool is None:
            if DATABASE_URL:
                cls._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    dsn=DATABASE_URL,
                    connect_timeout=5,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5,
                )
            else:
                cls._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    host=DATABASE_CONFIG["host"],
                    port=DATABASE_CONFIG["port"],
                    database=DATABASE_CONFIG["database"],
                    user=DATABASE_CONFIG["user"],
                    password=DATABASE_CONFIG["password"],
                    connect_timeout=5,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5,
                )
        return cls._pool

    @classmethod
    @contextmanager
    def get_connection(cls):
        """Context manager for getting a connection from the pool."""
        pool = cls.get_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            pool.putconn(conn)


def init_db():
    """Initialize database with required schema (pgvector extension, document_chunks)."""
    pool = DBPool.get_pool()
    conn = pool.getconn()
    try:
        cursor = conn.cursor()

        # Create pgvector extension
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Create document_chunks table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY,
                document_name VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                embedding vector(384) NOT NULL,
                source_file VARCHAR(255),
                chunk_index INTEGER DEFAULT 0,
                total_chunks INTEGER DEFAULT 1,
                content_tsv TSVECTOR,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create HNSW index for vector search if not exists
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
        """)

        # Create GIN index for full-text search (BM25) if not exists
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS document_chunks_fts_idx
            ON document_chunks
            USING GIN (content_tsv)
        """)

        # Create trigger to auto-update content_tsv on insert/update
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_content_tsv()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.content_tsv := to_tsvector('english', NEW.content);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)

        cursor.execute("""
            DROP TRIGGER IF EXISTS document_chunks_tsv_trigger ON document_chunks;
            CREATE TRIGGER document_chunks_tsv_trigger
            BEFORE INSERT OR UPDATE ON document_chunks
            FOR EACH ROW
            EXECUTE FUNCTION update_content_tsv()
        """)

        # Create chat_sessions table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                query_type VARCHAR(50) NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index on session_id for faster history retrieval
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS chat_sessions_session_id_idx
            ON chat_sessions (session_id)
        """)

        conn.commit()
        pool.putconn(conn)

        # Warm up the connection pool by creating minconn connections
        # This prevents the first request from waiting for connection establishment
        warmup_conn = pool.getconn()
        pool.putconn(warmup_conn)

        return True
    except Exception as e:
        pool.putconn(conn)
        raise e


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
