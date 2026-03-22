#!/usr/bin/env python
"""
Document Ingestion Script - Loads documents from data/docs folder into document_chunks table.

Usage:
    python script/ingest_documents.py
"""
import os
import re
import sys
from dotenv import load_dotenv

# Add project root and backend directory to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "backend"))
sys.path.insert(0, "/app")  # Container path

load_dotenv()

# Import after dotenv load
try:
    from database import DBPool, init_db
    from services.llm_client import llm_client
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    print("Make sure you're running from project root or have backend/ in Python path")
    sys.exit(1)


# Document directory - works both locally and in container
def get_docs_dir():
    """Get the docs directory path, works both locally and in container."""
    # Try container path first (/app/data/docs)
    container_path = "/app/data/docs"
    if os.path.exists(container_path):
        return container_path

    # Try relative path from script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    local_path = os.path.join(project_root, "data", "docs")
    if os.path.exists(local_path):
        return local_path

    # Fallback to relative path
    return "data/docs"

DOCS_DIR = get_docs_dir()

# Chunking configuration
CHUNK_SIZE_CHARS = 2000  # Approximate 500 tokens for English text
CHUNK_OVERLAP_CHARS = 70


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list:
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


def process_document(file_path: str) -> list:
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


def insert_chunks(chunks_with_embeddings: list) -> int:
    """Insert chunks with embeddings into database."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        from psycopg2.extras import execute_values
        records = [
            (
                chunk["document_name"],
                chunk["content"],
                embedding,
                chunk.get("source_file", ""),
                chunk.get("chunk_index", 0),
                chunk.get("total_chunks", 1)
            )
            for chunk, embedding in chunks_with_embeddings
        ]

        insert_query = """
            INSERT INTO document_chunks (document_name, content, embedding, source_file, chunk_index, total_chunks)
            VALUES %s
        """

        execute_values(cursor, insert_query, records)

        return len(records)


def generate_embeddings(chunks: list) -> list:
    """Generate embeddings for chunks."""
    embeddings = []
    for i, chunk in enumerate(chunks):
        print(f"  Generating embedding {i + 1}/{len(chunks)}...")
        embedding = llm_client.embed(chunk["content"])
        embeddings.append(embedding)
    return embeddings


def main():
    """Main function to ingest all documents."""
    print("=" * 60)
    print("Document Ingestion Script")
    print("=" * 60)

    # Initialize database
    print("\n1. Initializing database...")
    init_db()
    print("   Database initialized successfully.")

    # Check if docs directory exists
    if not os.path.exists(DOCS_DIR):
        print(f"\nERROR: Documents directory not found: {DOCS_DIR}")
        return

    # Process all documents
    print(f"\n2. Processing documents from {DOCS_DIR}...")
    all_chunks = []

    doc_files = [f for f in os.listdir(DOCS_DIR) if f.endswith('.md')]

    if not doc_files:
        print("   No .md files found in documents directory.")
        return

    for filename in doc_files:
        file_path = os.path.join(DOCS_DIR, filename)
        print(f"\n   Processing: {filename}")

        chunks = process_document(file_path)
        print(f"   - Created {len(chunks)} chunks")

        all_chunks.extend(chunks)

    print(f"\n   Total documents processed: {len(doc_files)}")
    print(f"   Total chunks created: {len(all_chunks)}")

    # Generate embeddings
    print(f"\n3. Generating embeddings for {len(all_chunks)} chunks...")
    embeddings = generate_embeddings(all_chunks)

    # Store chunks with embeddings
    chunks_with_embeddings = list(zip(all_chunks, embeddings))

    # Insert into database
    print("\n4. Inserting into database...")
    inserted = insert_chunks(chunks_with_embeddings)

    print(f"\n   Successfully inserted {inserted} chunks into document_chunks table")

    # Print sample
    print("\n5. Sample chunk (first):")
    if all_chunks:
        print(f"   Document: {all_chunks[0]['document_name']}")
        print(f"   Content preview: {all_chunks[0]['content'][:100]}...")
        print(f"   Source: {all_chunks[0]['source_file']}")
        print(f"   Chunk: {all_chunks[0]['chunk_index'] + 1}/{all_chunks[0]['total_chunks']}")

    print("\n" + "=" * 60)
    print("Document ingestion completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
