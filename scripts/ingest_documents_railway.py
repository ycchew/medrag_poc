"""
Document Ingestion Script for Railway - Loads documents into document_chunks table.

Usage:
    railway run python scripts/ingest_documents_railway.py

Or locally with Railway connection:
    export DATABASE_URL="your_railway_url"
    export LLM_API_KEY="your_key"
    python scripts/ingest_documents_railway.py
"""

import os
import re
import sys
from pathlib import Path

# Add project paths
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

# Get environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_API_URL = os.getenv("LLM_API_URL", "https://coding-intl.dashscope.aliyuncs.com")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.5-plus")

# Paths
DOCS_DIR = project_root / "data" / "docs"

# Chunking config
CHUNK_SIZE_CHARS = 2000
CHUNK_OVERLAP_CHARS = 70


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list:
    """Split text into chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        chunk = text[start:end]
        last_period = max(
            chunk.rfind("."), chunk.rfind("\n"), chunk.rfind("!"), chunk.rfind("?")
        )

        if last_period > len(chunk) * 0.8:
            end = start + last_period + 1

        chunks.append(text[start:end].strip())
        start = end - overlap if end > overlap else end

    return chunks


def remove_markdown_headers(text: str) -> str:
    """Remove markdown headers."""
    lines = text.split("\n")
    filtered_lines = [line for line in lines if not line.strip().startswith("#")]
    return "\n".join(filtered_lines)


def clean_text(text: str) -> str:
    """Clean text for embedding."""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("**", "").replace("*", "").replace("_", " ")
    return text.strip()


def process_document(file_path: str) -> list:
    """Process a document into chunks."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    filename = os.path.basename(file_path)
    doc_name = os.path.splitext(filename)[0].replace("_", " ").title()

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


def generate_embedding(text: str) -> list:
    """Generate embedding using LLM API."""
    import requests

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {"model": LLM_MODEL, "input": text}

    response = requests.post(
        f"{LLM_API_URL}/compatible-mode/v1/embeddings", headers=headers, json=payload
    )

    if response.status_code == 200:
        return response.json()["data"][0]["embedding"]
    else:
        raise Exception(f"Embedding failed: {response.text}")


def insert_chunks(chunks_with_embeddings: list, conn) -> int:
    """Insert chunks into database."""
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
    conn.commit()
    cursor.close()

    return len(records)


def main():
    """Main function."""
    print("=" * 60)
    print("Document Ingestion - Railway")
    print("=" * 60)

    if not DATABASE_URL:
        print("\nError: DATABASE_URL not set")
        print("Run with: railway run python scripts/ingest_documents_railway.py")
        sys.exit(1)

    if not LLM_API_KEY:
        print("\nError: LLM_API_KEY not set")
        sys.exit(1)

    if not DOCS_DIR.exists():
        print(f"\nError: Documents directory not found: {DOCS_DIR}")
        sys.exit(1)

    # Connect to database
    print("\nConnecting to Railway PostgreSQL...")
    import psycopg2

    conn = psycopg2.connect(DATABASE_URL)
    print("Connected!")

    # Process documents
    print(f"\nProcessing documents from {DOCS_DIR}...")
    all_chunks = []

    doc_files = [f for f in os.listdir(DOCS_DIR) if f.endswith(".md")]

    if not doc_files:
        print("No .md files found.")
        return

    for filename in doc_files:
        file_path = os.path.join(DOCS_DIR, filename)
        print(f"\nProcessing: {filename}")
        chunks = process_document(file_path)
        print(f"  Created {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"\nTotal: {len(doc_files)} documents, {len(all_chunks)} chunks")

    # Generate embeddings
    print(f"\nGenerating embeddings...")
    chunks_with_embeddings = []
    for i, chunk in enumerate(all_chunks):
        print(f"  {i + 1}/{len(all_chunks)}: {chunk['document_name']}...")
        try:
            embedding = generate_embedding(chunk["content"])
            chunks_with_embeddings.append((chunk, embedding))
        except Exception as e:
            print(f"    Error: {e}")
            continue

    # Insert into database
    print("\nInserting into database...")
    try:
        inserted = insert_chunks(chunks_with_embeddings, conn)
        print(f"\nSuccessfully inserted {inserted} chunks")
    except Exception as e:
        print(f"\nError inserting: {e}")
        raise
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("Document ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
