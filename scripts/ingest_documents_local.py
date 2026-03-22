#!/usr/bin/env python
"""
Document Ingestion Script - Loads documents from data/docs folder into document_chunks table.

Local version - runs without Docker.
Usage: python scripts/ingest_documents_local.py
"""

import os
import re
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

# Document directory - local paths only
DOCS_DIR = project_root / "data" / "docs"

# Import after path setup
try:
    from database import DBPool, init_db
    from services.llm_client import llm_client
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    print("Make sure you're running from project root or have backend/ in Python path")
    sys.exit(1)

# Chunking configuration
CHUNK_SIZE_CHARS = 2000  # Approximate 500 tokens for English text
CHUNK_OVERLAP_CHARS = 70


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list:
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
            chunk.rfind("."), chunk.rfind("\n"), chunk.rfind("!"), chunk.rfind("?")
        )

        if last_period > len(chunk) * 0.8:  # Only break at sentence end if past 80%
            end = start + last_period + 1

        chunks.append(text[start:end].strip())
        start = end - overlap if end > overlap else end

    return chunks


def remove_markdown_headers(text: str) -> str:
    """Remove markdown headers to reduce noise in embeddings."""
    lines = text.split("\n")
    filtered_lines = [line for line in lines if not line.strip().startswith("#")]
    return "\n".join(filtered_lines)


def clean_text(text: str) -> str:
    """Clean and normalize text for embedding."""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("**", "").replace("*", "").replace("_", " ")
    return text.strip()


def process_document(file_path: str) -> list:
    """Process a single document file and return chunks."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    filename = os.path.basename(file_path)
    doc_name = os.path.splitext(filename)[0].replace("_", " ").title()

    # Clean and chunk the document
    cleaned = clean_text(remove_markdown_headers(content))
    chunks = chunk_text(cleaned)

    return [
        {
            "document_name": doc_name,
            "content": chunk,
            "source_file": filename,
            "chunk_index": i,
            "total_chunks": len(chunks),
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
                chunk.get("total_chunks", 1),
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
    print("Document Ingestion Script (Local)")
    print("=" * 60)

    # Check if docs directory exists
    if not DOCS_DIR.exists():
        print(f"\nERROR: Documents directory not found: {DOCS_DIR}")
        print("Please ensure data/docs/ exists with .md files")
        return

    # Initialize database (skip if already set up)
    print("\n1. Checking database...")
    try:
        init_db()
        print("   Database initialized successfully.")
    except Exception as e:
        error_msg = str(e).lower()
        # Common errors when DB is already set up or user lacks extension create permission
        if "already exists" in error_msg or "permission denied" in error_msg:
            print("   Database already initialized (skipping setup).")
        else:
            print(f"   Database init warning: {e}")
            print("   Continuing with document ingestion...")

    # Process all documents
    print(f"\n2. Processing documents from {DOCS_DIR}...")
    all_chunks = []

    doc_files = [f for f in os.listdir(DOCS_DIR) if f.endswith(".md")]

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
    try:
        embeddings = generate_embeddings(all_chunks)
    except Exception as e:
        print(f"\nError generating embeddings: {e}")
        print("\nTroubleshooting:")
        print("  1. Check LLM_API_KEY is set in .env")
        print("  2. Verify LLM_API_URL is correct")
        print("  3. Ensure network connectivity to LLM service")
        return

    # Store chunks with embeddings
    chunks_with_embeddings = list(zip(all_chunks, embeddings))

    # Insert into database
    print("\n4. Inserting into database...")
    try:
        inserted = insert_chunks(chunks_with_embeddings)
        print(
            f"\n   Successfully inserted {inserted} chunks into document_chunks table"
        )
    except Exception as e:
        print(f"\nError inserting chunks: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure init_schema.sql has been run")
        print("  2. Check database has document_chunks table")
        print("  3. Verify pgvector extension is installed")
        return

    # Print sample
    print("\n5. Sample chunk (first):")
    if all_chunks:
        print(f"   Document: {all_chunks[0]['document_name']}")
        print(f"   Content preview: {all_chunks[0]['content'][:100]}...")
        print(f"   Source: {all_chunks[0]['source_file']}")
        print(
            f"   Chunk: {all_chunks[0]['chunk_index'] + 1}/{all_chunks[0]['total_chunks']}"
        )

    print("\n" + "=" * 60)
    print("Document ingestion completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
