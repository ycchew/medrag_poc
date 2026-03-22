"""
Document RAG Service - Handles document chunking, embedding, and vector search.
"""
import os
import re
import time
import logging
from typing import List, Dict, Any
from services.llm_client import llm_client
from database import DBPool

logger = logging.getLogger(__name__)

# Chunking configuration
CHUNK_SIZE_TOKENS = 500
CHUNK_SIZE_CHARS = 2000  # Approximate 500 tokens
CHUNK_OVERLAP_CHARS = 200


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> List[str]:
    """
    Split text into chunks based on character count.
    Preserves sentence boundaries where possible.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Try to find a sentence boundary near the chunk end
        chunk = text[start:end]
        last_period = max(
            chunk.rfind('.'),
            chunk.rfind('\n'),
            chunk.rfind('!'),
            chunk.rfind('?')
        )

        if last_period > len(chunk) * 0.8:  # Only break at sentence end if past 80%
            end = start + last_period + 1

        chunks.append(text[start:end].strip())
        start = end - overlap if end > overlap else end

    return chunks


def remove_markdown_headers(text: str) -> str:
    """Remove markdown headers to reduce noise in embeddings."""
    lines = text.split('\n')
    filtered_lines = [line for line in lines if not line.strip().startswith('#')]
    return '\n'.join(filtered_lines)


def clean_text(text: str) -> str:
    """Clean and normalize text for embedding."""
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('**', '').replace('*', '').replace('_', ' ')
    return text.strip()


def process_document(file_path: str) -> List[Dict[str, Any]]:
    """Process a single document file and return chunks."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    filename = os.path.basename(file_path)
    doc_name = os.path.splitext(filename)[0].replace('_', ' ').title()

    # Clean and chunk the document
    cleaned = clean_text(remove_markdown_headers(content))
    chunks = chunk_text(cleaned)

    return [
        {
            "document_name": doc_name,
            "content": chunk,
            "source_file": filename,
            "chunk_index": i,
            "total_chunks": len(chunks)
        }
        for i, chunk in enumerate(chunks)
    ]


def generate_embeddings_for_chunks(chunks: List[Dict[str, Any]]) -> List[List[float]]:
    """Generate embeddings for all chunks."""
    embeddings = []
    for chunk in chunks:
        embedding = llm_client.embed(chunk["content"])
        embeddings.append(embedding)
    return embeddings


def insert_document_chunks(chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> int:
    """Insert chunks with embeddings into database."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        records = [
            (
                chunk["document_name"],
                chunk["content"],
                embedding,
                chunk.get("source_file", ""),
                chunk.get("chunk_index", 0),
                chunk.get("total_chunks", 1)
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        insert_query = """
            INSERT INTO document_chunks (document_name, content, embedding, source_file, chunk_index, total_chunks)
            VALUES %s
        """

        from psycopg2.extras import execute_values
        execute_values(cursor, insert_query, records)

        return len(records)


def vector_search(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Search document_chunks using vector cosine similarity.

    Returns top_k most similar chunks.
    """
    total_start = time.time()

    # Generate embedding for query
    t0 = time.time()
    query_embedding = llm_client.embed(query)
    t1 = time.time()
    logger.info(f"[TIMING] Embedding generation: {t1-t0:.3f}s")

    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        # Convert embedding to text format for PostgreSQL
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

        t0 = time.time()
        cursor.execute("""
            SELECT document_name, content, source_file, chunk_index, total_chunks,
                   1 - (embedding <=> %s::vector) as similarity
            FROM document_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (embedding_str, embedding_str, top_k))

        rows = cursor.fetchall()
        t1 = time.time()
        logger.info(f"[TIMING] Vector DB query: {t1-t0:.3f}s")

        total_time = time.time() - total_start
        logger.info(f"[TIMING] Total vector_search: {total_time:.3f}s")

        return [
            {
                "document_name": row[0],
                "content": row[1],
                "source_file": row[2],
                "chunk_index": row[3],
                "total_chunks": row[4],
                "similarity": float(row[5])
            }
            for row in rows
        ]


def hybrid_search(query: str, top_k: int = 5, bm25_weight: float = 0.3) -> List[Dict[str, Any]]:
    """
    Hybrid search combining BM25 (keyword) + Vector (semantic) scores.

    Args:
        query: User's search query
        top_k: Number of results to return
        bm25_weight: Weight for BM25 score (0-1), rest goes to vector

    Returns:
        List of chunks ranked by combined score
    """
    total_start = time.time()

    # Generate embedding for query (for vector search)
    t0 = time.time()
    query_embedding = llm_client.embed(query)
    t1 = time.time()
    logger.info(f"[TIMING] Embedding generation: {t1-t0:.3f}s")

    # Convert embedding to text format for PostgreSQL
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    # Prepare full-text search query terms (OR between words)
    search_terms = ' | '.join(query.lower().split())

    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        t0 = time.time()
        # Combined query: BM25 + Vector scores with weighted combination
        cursor.execute("""
            WITH bm25_matches AS (
                SELECT
                    id,
                    document_name,
                    content,
                    source_file,
                    chunk_index,
                    total_chunks,
                    embedding,
                    COALESCE(ts_rank(content_tsv, plainto_tsquery('english', %s)), 0) as bm25_score
                FROM document_chunks
                WHERE content_tsv @@ plainto_tsquery('english', %s)
            ),
            all_chunks AS (
                SELECT
                    id,
                    document_name,
                    content,
                    source_file,
                    chunk_index,
                    total_chunks,
                    embedding,
                    0 as bm25_score
                FROM document_chunks
                WHERE id NOT IN (SELECT id FROM bm25_matches)
            ),
            combined AS (
                SELECT
                    id,
                    document_name,
                    content,
                    source_file,
                    chunk_index,
                    total_chunks,
                    bm25_score,
                    1 - (embedding <=> %s::vector) as vector_score
                FROM bm25_matches
                UNION ALL
                SELECT
                    id,
                    document_name,
                    content,
                    source_file,
                    chunk_index,
                    total_chunks,
                    bm25_score,
                    1 - (embedding <=> %s::vector) as vector_score
                FROM all_chunks
            ),
            scored AS (
                SELECT
                    document_name,
                    content,
                    source_file,
                    chunk_index,
                    total_chunks,
                    bm25_score,
                    vector_score,
                    (bm25_score * %s + vector_score * (1 - %s)) as combined_score
                FROM combined
            )
            SELECT
                document_name,
                content,
                source_file,
                chunk_index,
                total_chunks,
                combined_score
            FROM scored
            ORDER BY combined_score DESC
            LIMIT %s
        """, (query, query, embedding_str, embedding_str, bm25_weight, bm25_weight, top_k))

        rows = cursor.fetchall()
        t1 = time.time()
        logger.info(f"[TIMING] Hybrid DB query: {t1-t0:.3f}s")

        total_time = time.time() - total_start
        logger.info(f"[TIMING] Total hybrid_search: {total_time:.3f}s")

        return [
            {
                "document_name": row[0],
                "content": row[1],
                "source_file": row[2],
                "chunk_index": row[3],
                "total_chunks": row[4],
                "bm25_score": float(row[5]) if len(rows[0]) > 5 else 0.0,
                "vector_score": float(row[6]) if len(rows[0]) > 6 else float(row[5]),
                "similarity": float(row[5])  # Use combined score as similarity
            }
            for row in rows
        ]


def format_retrieved_chunks_for_prompt(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks for inclusion in LLM prompt as markdown."""
    formatted = []
    for i, chunk in enumerate(chunks, 1):
        formatted.append(
            f"## Source: {chunk['document_name']} (Chunk {chunk['chunk_index']+1}/{chunk['total_chunks']})\n\n"
            f"**Similarity:** {chunk['similarity']:.3f}\n\n"
            f"{chunk['content'][:2000]}\n\n"
            f"---\n"
        )
    return "\n".join(formatted)


if __name__ == "__main__":
    # Test document processing
    docs_dir = "../data/docs"
    if os.path.exists(docs_dir):
        for filename in os.listdir(docs_dir):
            if filename.endswith('.md'):
                file_path = os.path.join(docs_dir, filename)
                chunks = process_document(file_path)
                print(f"{filename}: {len(chunks)} chunks created")
