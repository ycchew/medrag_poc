#!/usr/bin/env python
"""
BM25 Migration Script - Adds full-text search support to existing document_chunks.

Local version - runs without Docker.
Usage: python scripts/migrate_bm25_local.py
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using system environment variables.")
    print("Install with: pip install python-dotenv")

# Override database host for local development (before importing backend)
os.environ["DATABASE_HOST"] = "localhost"

# Add project root and backend directory to path for imports
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

try:
    from database import DBPool
except ImportError as e:
    print(f"Error importing database module: {e}")
    print("Make sure you're running from project root or have backend/ in Python path")
    sys.exit(1)


def migrate_bm25():
    """
    Add BM25 full-text search support to existing document_chunks table.
    This is a one-time migration for existing databases.
    """
    print("=" * 60)
    print("BM25 Migration Script (Local)")
    print("=" * 60)

    try:
        with DBPool.get_connection() as conn:
            cursor = conn.cursor()

            # Step 1: Add content_tsv column if not exists
            print("\n1. Adding content_tsv column...")
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'document_chunks' AND column_name = 'content_tsv'
            """)
            if cursor.fetchone():
                print("   Column content_tsv already exists.")
            else:
                cursor.execute("""
                    ALTER TABLE document_chunks
                    ADD COLUMN content_tsv TSVECTOR
                """)
                print("   Column content_tsv added.")

            # Step 2: Create trigger function
            print("\n2. Creating trigger function...")
            cursor.execute("""
                CREATE OR REPLACE FUNCTION update_content_tsv()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.content_tsv := to_tsvector('english', NEW.content);
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
            """)
            print("   Trigger function created.")

            # Step 3: Create trigger
            print("\n3. Creating trigger...")
            cursor.execute("""
                DROP TRIGGER IF EXISTS document_chunks_tsv_trigger ON document_chunks;
                CREATE TRIGGER document_chunks_tsv_trigger
                BEFORE INSERT OR UPDATE ON document_chunks
                FOR EACH ROW
                EXECUTE FUNCTION update_content_tsv()
            """)
            print("   Trigger created.")

            # Step 4: Create GIN index
            print("\n4. Creating GIN index...")
            cursor.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'document_chunks' AND indexname = 'document_chunks_fts_idx'
            """)
            if cursor.fetchone():
                print("   GIN index already exists.")
            else:
                cursor.execute("""
                    CREATE INDEX document_chunks_fts_idx
                    ON document_chunks USING GIN (content_tsv)
                """)
                print("   GIN index created.")

            conn.commit()
    except Exception as e:
        print(f"\nError during schema migration: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure PostgreSQL is running locally")
        print("  2. Check .env file has correct credentials")
        print("  3. Verify document_chunks table exists")
        sys.exit(1)

    # Step 5: Populate content_tsv for existing data
    print("\n5. Populating content_tsv for existing chunks...")
    try:
        with DBPool.get_connection() as conn:
            cursor = conn.cursor()

            # Count total chunks
            cursor.execute("SELECT COUNT(*) FROM document_chunks")
            total = cursor.fetchone()[0]
            print(f"   Total chunks in database: {total}")

            if total == 0:
                print("   No chunks to migrate.")
                return

            # Count chunks that need updating
            cursor.execute(
                "SELECT COUNT(*) FROM document_chunks WHERE content_tsv IS NULL"
            )
            to_update = cursor.fetchone()[0]
            print(f"   Chunks to update: {to_update}")

            if to_update > 0:
                # Update chunks that don't have content_tsv populated
                cursor.execute("""
                    UPDATE document_chunks
                    SET content_tsv = to_tsvector('english', content)
                    WHERE content_tsv IS NULL
                """)
                conn.commit()
                print(f"   Updated {to_update} chunks with BM25 vectors.")
            else:
                print("   All chunks already have BM25 vectors.")

            # Count final
            cursor.execute(
                "SELECT COUNT(*) FROM document_chunks WHERE content_tsv IS NOT NULL"
            )
            updated = cursor.fetchone()[0]
            print(f"   Total chunks with BM25: {updated}/{total}")
    except Exception as e:
        print(f"\nError populating BM25 data: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("BM25 hybrid search is now available.")
    print("=" * 60)


if __name__ == "__main__":
    migrate_bm25()
