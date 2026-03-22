#!/usr/bin/env python3
"""
Clinic AI Assistant - Initialization Script

This script orchestrates the complete setup process:
1. Initialize relational schema (SQL tables)
2. Import synthetic data from CSV
3. Adjust visit patterns (Monday/Friday boost)
4. Ingest documents for RAG (requires LLM_API_KEY)
5. Add BM25 full-text search support

Usage (from host):
    python scripts/init-me.py [--skip-data] [--skip-docs] [--skip-bm25]

Usage (from inside container):
    docker exec clinic_backend python scripts/init-me.py

Options:
    --skip-data    Skip relational data import (steps 1-3)
    --skip-docs    Skip document ingestion (step 4)
    --skip-bm25    Skip BM25 migration (step 5)

Prerequisites:
    - Docker containers must be running: docker compose up -d
    - LLM_API_KEY must be set in .env for document ingestion
"""
import os
import sys
import subprocess
import argparse
import time
from pathlib import Path

# Detect if running inside Docker container
def is_running_in_container():
    """Check if we're running inside a Docker container."""
    # Check for .dockerenv file
    if Path("/.dockerenv").exists():
        return True
    # Check cgroup for docker
    try:
        with open("/proc/self/cgroup", "r") as f:
            return "docker" in f.read()
    except:
        pass
    return False

IN_CONTAINER = is_running_in_container()

# Path configuration
if IN_CONTAINER:
    # Running inside container
    SCRIPT_DIR = Path("/app/scripts")
    PROJECT_ROOT = Path("/app")
    DATA_DIR = Path("/app/data")
else:
    # Running from host
    SCRIPT_DIR = Path(__file__).parent.resolve()
    PROJECT_ROOT = SCRIPT_DIR.parent
    DATA_DIR = PROJECT_ROOT / "data"

SQL_DIR = DATA_DIR / "sql"
DOCS_DIR = DATA_DIR / "docs"

# Add backend to path for imports
BACKEND_DIR = PROJECT_ROOT / "backend" if not IN_CONTAINER else Path("/app")
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def run_command(cmd, description, exit_on_error=True):
    """Run a shell command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")

    result = subprocess.run(cmd, shell=True, capture_output=False)

    if result.returncode != 0:
        print(f"\n[ERROR] Failed: {description}")
        if exit_on_error:
            sys.exit(1)
        return False

    print(f"\n[SUCCESS] {description}")
    return True


def run_python_script(script_name, description):
    """Run a Python script, either directly or via docker exec."""
    if IN_CONTAINER:
        # Run directly
        cmd = f"python scripts/{script_name}"
    else:
        # Run via docker exec
        cmd = f"docker exec clinic_backend python scripts/{script_name}"
    return run_command(cmd, description)


def check_containers():
    """Check if required Docker containers are running."""
    if IN_CONTAINER:
        # Inside container, just check if we can connect to DB
        print("Running inside container, skipping container checks...")
        return True

    print("Checking Docker containers...")

    result = subprocess.run(
        "docker ps --format '{{.Names}}' | grep -E 'clinic_postgres|clinic_backend'",
        shell=True, capture_output=True, text=True
    )

    containers = result.stdout.strip().split('\n')
    containers = [c for c in containers if c]

    if len(containers) < 2:
        print("[ERROR] Required containers are not running!")
        print("Please start them first:")
        print("  docker compose up -d --build")
        sys.exit(1)

    print(f"  Found containers: {', '.join(containers)}")
    return True


def check_env_file():
    """Check if .env file exists and has required variables."""
    if IN_CONTAINER:
        # Inside container, check environment variables directly
        llm_key = os.getenv("LLM_API_KEY")
        if llm_key:
            print("  [OK] LLM_API_KEY environment variable set")
            return True
        else:
            print("  [WARNING] LLM_API_KEY not set in environment")
            return False

    env_file = PROJECT_ROOT / ".env"

    if not env_file.exists():
        print("[WARNING] .env file not found at project root!")
        print("Please create one from .env.example or ensure environment variables are set.")
        return False

    print(f"  Found .env file")
    return True


def check_csv_files():
    """Check if required CSV files exist."""
    required_files = [
        "clinics.csv",
        "patients.csv",
        "visits.csv",
        "diagnoses.csv",
        "prescriptions.csv",
        "clinical_notes.csv"
    ]

    print("Checking CSV data files...")
    missing = []
    for fname in required_files:
        fpath = SQL_DIR / fname
        if fpath.exists():
            print(f"  [OK] {fname}")
        else:
            print(f"  [MISSING] {fname}")
            missing.append(fname)

    if missing:
        print(f"\n[ERROR] Missing CSV files: {', '.join(missing)}")
        print("Generate them first from the host:")
        print("  python scripts/generate_synthetic_data.py")
        print("  python scripts/generate_clinic_notes.py")
        return False

    return True


def check_doc_files():
    """Check if document files exist."""
    print("Checking document files...")

    if not DOCS_DIR.exists():
        print(f"  [MISSING] Docs directory: {DOCS_DIR}")
        return False

    md_files = list(DOCS_DIR.glob("*.md"))
    if not md_files:
        print(f"  [WARNING] No .md files found in {DOCS_DIR}")
        return False

    print(f"  [OK] Found {len(md_files)} document files")
    for f in md_files:
        print(f"    - {f.name}")

    return True


def step1_init_schema():
    """Initialize relational schema."""
    schema_file = SQL_DIR / "init_schema.sql"

    if not schema_file.exists():
        print(f"[ERROR] Schema file not found: {schema_file}")
        sys.exit(1)

    if IN_CONTAINER:
        # Inside container: execute SQL directly via psycopg2
        print("\n" + "="*60)
        print("Step: Initialize relational schema")
        print("="*60)

        try:
            import psycopg2
            from config import DATABASE_CONFIG

            conn = psycopg2.connect(**DATABASE_CONFIG)
            conn.autocommit = True
            cursor = conn.cursor()

            with open(schema_file, 'r') as f:
                sql = f.read()
                cursor.execute(sql)

            cursor.close()
            conn.close()
            print("\n[SUCCESS] Relational schema initialized")
            return True
        except Exception as e:
            print(f"\n[ERROR] Failed to initialize schema: {e}")
            sys.exit(1)
    else:
        # From host: use docker exec with psql
        cmd = f"docker exec -i clinic_postgres psql -U clinic_user -d clinic_db < {schema_file}"
        return run_command(cmd, "Initialize relational schema")


def step2_import_data():
    """Import CSV data."""
    return run_python_script("import_csv_data.py", "Import synthetic data from CSV")


def step3_adjust_visits():
    """Adjust visit patterns for Monday/Friday."""
    return run_python_script("adjust_visits_by_day.py", "Adjust visit patterns (Monday/Friday boost)")


def step4_ingest_docs():
    """Ingest documents for RAG."""
    return run_python_script("ingest_documents.py", "Ingest documents for RAG (requires LLM_API_KEY)")


def step5_migrate_bm25():
    """Add BM25 full-text search."""
    return run_python_script("migrate_bm25.py", "Add BM25 full-text search support")


def main():
    parser = argparse.ArgumentParser(
        description="Clinic AI Assistant - Complete Initialization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # From host - full setup
    python scripts/init-me.py

    # From host - then inside container
    docker compose up -d --build
    docker exec clinic_backend python scripts/init-me.py

    # Skip data import (if already imported)
    python scripts/init-me.py --skip-data

    # Only ingest documents
    python scripts/init-me.py --skip-data --skip-bm25
        """
    )
    parser.add_argument(
        "--skip-data",
        action="store_true",
        help="Skip relational data import (steps 1-3)"
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip document ingestion (step 4)"
    )
    parser.add_argument(
        "--skip-bm25",
        action="store_true",
        help="Skip BM25 migration (step 5)"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check prerequisites, don't run setup"
    )

    args = parser.parse_args()

    # Header
    print("="*60)
    print("Clinic AI Assistant - Initialization Script")
    if IN_CONTAINER:
        print("(Running inside Docker container)")
    else:
        print("(Running from host)")
    print("="*60)
    print()

    # Pre-flight checks
    print("Running pre-flight checks...")
    print("-"*60)

    check_containers()
    check_env_file()

    if not args.skip_data:
        check_csv_files()

    if not args.skip_docs:
        check_doc_files()

    print("-"*60)
    print("[OK] Pre-flight checks passed")
    print()

    if args.check_only:
        print("--check-only specified, exiting without making changes.")
        sys.exit(0)

    # Confirm before proceeding
    print("Setup plan:")
    steps = []
    if not args.skip_data:
        steps.extend([
            "1. Initialize relational schema (SQL tables)",
            "2. Import synthetic data from CSV",
            "3. Adjust visit patterns (Monday/Friday boost)",
        ])
    if not args.skip_docs:
        steps.append("4. Ingest documents for RAG (requires LLM_API_KEY)")
    if not args.skip_bm25:
        steps.append("5. Add BM25 full-text search support")

    for step in steps:
        print(f"  {step}")

    print()
    response = input("Proceed with setup? [y/N]: ")
    if response.lower() not in ['y', 'yes']:
        print("Setup cancelled.")
        sys.exit(0)

    # Execute steps
    start_time = time.time()

    try:
        if not args.skip_data:
            step1_init_schema()
            step2_import_data()
            step3_adjust_visits()

        if not args.skip_docs:
            step4_ingest_docs()

        if not args.skip_bm25:
            step5_migrate_bm25()

    except KeyboardInterrupt:
        print("\n\n[WARNING] Setup interrupted by user!")
        sys.exit(1)

    # Summary
    elapsed = time.time() - start_time
    print()
    print("="*60)
    print("SETUP COMPLETE!")
    print("="*60)
    print(f"Total time: {elapsed:.1f} seconds")
    print()
    print("The Clinic AI Assistant is ready to use:")
    print("  Frontend: http://localhost:3000")
    print("  Backend API: http://localhost:8000")
    print("  API Docs: http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    main()
