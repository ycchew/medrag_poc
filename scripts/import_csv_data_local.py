"""
Import CSV data into local PostgreSQL database (non-Docker setup).

Usage:
    python scripts/import_csv_data_local.py

Prerequisites:
    1. PostgreSQL with pgvector extension running locally
    2. Run data/sql/init_schema.sql to create tables
    3. CSV files exist in data/sql/
    4. Environment variables set in .env file
"""

import os
import sys
import csv
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using system environment variables.")
    print("Install with: pip install python-dotenv")

# Determine project root and data directory for local setup
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
DATA_DIR = project_root / "data"
SQL_DIR = DATA_DIR / "sql"

# Database configuration from .env (with local defaults)
DATABASE_CONFIG = {
    "host": os.getenv("DATABASE_HOST", "localhost"),  # Use localhost for local dev
    "port": int(os.getenv("DATABASE_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "clinic_db"),
    "user": os.getenv("POSTGRES_USER", "clinic_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "clinic_password"),
}

# Try to import local backend modules
backend_path = str(project_root / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from config import DATABASE_CONFIG as CONFIG_DB_CONFIG
    from database import DBPool, init_db

    DATABASE_CONFIG = CONFIG_DB_CONFIG  # Override with config.py if available
    # Force localhost for local development (override Docker 'db' hostname)
    DATABASE_CONFIG["host"] = "localhost"
    print("Using database configuration from backend.config (with localhost override)")
except ImportError:
    print("Using database configuration from environment variables")
    try:
        import psycopg2
    except ImportError:
        print("Error: psycopg2 is required. Install with: pip install psycopg2-binary")
        sys.exit(1)


def parse_date(date_str):
    """Parse date string to date object."""
    if not date_str:
        return None
    # Try different date formats
    formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def import_table_csv(cursor, table_name, csv_path, date_columns=None):
    """
    Import a CSV file into a database table using standard library csv module.

    Args:
        cursor: Database cursor
        table_name: Target table name
        csv_path: Path to CSV file
        date_columns: List of column names to parse as dates
    """
    print(f"Importing {table_name} from {csv_path}...")

    date_columns = date_columns or []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames

        if not columns:
            raise ValueError(f"No columns found in {csv_path}")

        placeholders = ",".join(["%s"] * len(columns))
        column_names = ",".join(columns)

        count = 0
        for row in reader:
            # Convert date columns
            values = []
            for col in columns:
                val = row.get(col)
                if col in date_columns and val:
                    val = parse_date(val)
                values.append(val)

            cursor.execute(
                f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})",
                values,
            )
            count += 1
            if count % 1000 == 0:
                print(f"  ... inserted {count} rows")

    print(f"  Completed: {count} rows imported into {table_name}")
    return count


def import_all_data():
    """Import all CSV files into the local database."""
    # Import order matters for foreign key constraints
    import_order = [
        ("clinics", "clinics.csv", None),
        ("patients", "patients.csv", ["dob"]),  # dob is a date
        ("visits", "visits.csv", ["visit_date"]),  # visit_date must be DATE
        ("diagnoses", "diagnoses.csv", None),
        ("prescriptions", "prescriptions.csv", None),
        ("clinical_notes", "clinical_notes.csv", None),
    ]

    print(f"Looking for CSV files in: {SQL_DIR}")

    # Check CSV files exist
    missing_files = []
    for _, csv_file, _ in import_order:
        csv_path = SQL_DIR / csv_file
        if not csv_path.exists():
            missing_files.append(str(csv_path))

    if missing_files:
        print(f"\nError: Missing required CSV files:")
        for f in missing_files:
            print(f"  - {f}")
        print(f"\nPlease ensure data files exist in {SQL_DIR}")
        sys.exit(1)

    conn = None
    cursor = None
    try:
        # Use DBPool if available, otherwise direct psycopg2
        if "DBPool" in globals():
            print("Using DBPool connection...")
            with DBPool.get_connection() as conn:
                cursor = conn.cursor()
                total_rows = 0
                for table_name, csv_file, date_cols in import_order:
                    csv_path = SQL_DIR / csv_file
                    total_rows += import_table_csv(
                        cursor, table_name, str(csv_path), date_cols
                    )

                # Reset SERIAL sequences for tables with auto-increment IDs
                print("\nResetting SERIAL sequences...")
                cursor.execute("SELECT MAX(visit_id) FROM visits")
                max_visit_id = cursor.fetchone()[0] or 0
                cursor.execute(
                    f"ALTER SEQUENCE visits_visit_id_seq RESTART WITH {max_visit_id + 1}"
                )
                print(f"  visits_visit_id_seq reset to {max_visit_id + 1}")

                conn.commit()
                print(f"\nTotal rows imported: {total_rows}")
        else:
            print(
                f"Connecting to PostgreSQL at {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}..."
            )
            import psycopg2

            conn = psycopg2.connect(**DATABASE_CONFIG)
            cursor = conn.cursor()
            print(f"Connected to database: {DATABASE_CONFIG['database']}")

            total_rows = 0
            for table_name, csv_file, date_cols in import_order:
                csv_path = SQL_DIR / csv_file
                total_rows += import_table_csv(
                    cursor, table_name, str(csv_path), date_cols
                )

            # Reset SERIAL sequences for tables with auto-increment IDs
            print("\nResetting SERIAL sequences...")
            cursor.execute("SELECT MAX(visit_id) FROM visits")
            max_visit_id = cursor.fetchone()[0] or 0
            cursor.execute(
                f"ALTER SEQUENCE visits_visit_id_seq RESTART WITH {max_visit_id + 1}"
            )
            print(f"  visits_visit_id_seq reset to {max_visit_id + 1}")

            conn.commit()
            print(f"\nTotal rows imported: {total_rows}")

    except Exception as e:
        # Check if it's a database-related error
        error_str = str(e).lower()
        if (
            "could not connect" in error_str
            or "connection" in error_str
            or "host" in error_str
            or "port" in error_str
            or "password" in error_str
            or "authentication" in error_str
        ):
            print(f"\nDatabase connection error: {e}")
            print("\nTroubleshooting:")
            print("  1. Ensure PostgreSQL is running locally")
            print("  2. Check .env file has correct credentials")
            print("  3. Verify database and user exist")
            print(
                f"  4. Current config: host={DATABASE_CONFIG['host']}, db={DATABASE_CONFIG['database']}"
            )
            sys.exit(1)
        else:
            print(f"\nError importing data: {e}")
            raise
        print(f"\nError importing data: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("\nDatabase connection closed.")


def verify_date_types():
    """Verify that visit_date is correctly stored as DATE type."""
    conn = None
    cursor = None
    try:
        if "DBPool" in globals():
            with DBPool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'visits' AND column_name = 'visit_date'
                """)
                result = cursor.fetchone()
                if result:
                    print(
                        f"\nVerification: visits.visit_date column type = {result[1]}"
                    )
                else:
                    print("\nWarning: Could not verify visits.visit_date column type")
        else:
            import psycopg2

            conn = psycopg2.connect(**DATABASE_CONFIG)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'visits' AND column_name = 'visit_date'
            """)
            result = cursor.fetchone()
            if result:
                print(f"\nVerification: visits.visit_date column type = {result[1]}")
            else:
                print("\nWarning: Could not verify visits.visit_date column type")
    except Exception as e:
        print(f"Could not verify date types: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Clinic AI Assistant - CSV Data Import (Local)")
    print("=" * 60)
    print()
    print("Prerequisites:")
    print("  1. PostgreSQL with pgvector running locally")
    print("  2. Run data/sql/init_schema.sql to create tables")
    print("  3. CSV files exist in data/sql/")
    print(
        f"  4. Database: {DATABASE_CONFIG['database']} @ {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}"
    )
    print()

    import_all_data()
    verify_date_types()

    print()
    print("Import complete!")
