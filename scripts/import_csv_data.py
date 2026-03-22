"""
Import CSV data into PostgreSQL with proper type casting.
Ensures visit_date is imported as DATE type.

Usage:
    python scripts/import_csv_data.py

Prerequisites:
    1. Run data/sql/init_schema.sql to create tables
    2. CSV files exist in data/sql/
"""
import os
import sys
import csv
from datetime import datetime
from pathlib import Path

# Determine project root and data directory
def get_data_dir():
    """Get the data directory path, works both locally and in container."""
    # Try container path first (/app/data)
    container_path = "/app/data"
    if os.path.exists(container_path):
        return container_path

    # Try relative path from script location
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    local_path = project_root / "data"
    if local_path.exists():
        return str(local_path)

    # Fallback to relative path
    return "data"

DATA_DIR = get_data_dir()
SQL_DIR = os.path.join(DATA_DIR, "sql")

# Add backend to path for imports
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
backend_paths = [
    str(project_root / "backend"),
    "/app",  # Container path
    ".",  # Current directory
]
for path in backend_paths:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

try:
    from config import DATABASE_CONFIG
    from database import DBPool, init_db
except ImportError:
    # Fallback to direct psycopg2 connection
    import psycopg2
    DATABASE_CONFIG = {
        "host": os.getenv("DATABASE_HOST", "localhost"),
        "port": int(os.getenv("DATABASE_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "clinic_db"),
        "user": os.getenv("POSTGRES_USER", "clinic_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "clinic_password"),
    }


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

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames

        if not columns:
            raise ValueError(f"No columns found in {csv_path}")

        placeholders = ','.join(['%s'] * len(columns))
        column_names = ','.join(columns)

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
                values
            )
            count += 1
            if count % 1000 == 0:
                print(f"  ... inserted {count} rows")

    print(f"  Completed: {count} rows imported into {table_name}")
    return count


def import_all_data():
    """Import all CSV files into the database."""
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

    try:
        # Use DBPool if available, otherwise direct psycopg2
        if 'DBPool' in globals():
            with DBPool.get_connection() as conn:
                cursor = conn.cursor()
                total_rows = 0
                for table_name, csv_file, date_cols in import_order:
                    csv_path = os.path.join(SQL_DIR, csv_file)
                    if os.path.exists(csv_path):
                        total_rows += import_table_csv(cursor, table_name, csv_path, date_cols)
                    else:
                        print(f"  Warning: {csv_path} not found, skipping")

                # Reset SERIAL sequences for tables with auto-increment IDs
                print("\nResetting SERIAL sequences...")
                cursor.execute("SELECT MAX(visit_id) FROM visits")
                max_visit_id = cursor.fetchone()[0] or 0
                cursor.execute(f"ALTER SEQUENCE visits_visit_id_seq RESTART WITH {max_visit_id + 1}")
                print(f"  visits_visit_id_seq reset to {max_visit_id + 1}")

                conn.commit()
                print(f"\nTotal rows imported: {total_rows}")
        else:
            # Fallback to direct connection
            conn = psycopg2.connect(**DATABASE_CONFIG)
            cursor = conn.cursor()

            total_rows = 0
            for table_name, csv_file, date_cols in import_order:
                csv_path = os.path.join(SQL_DIR, csv_file)
                if os.path.exists(csv_path):
                    total_rows += import_table_csv(cursor, table_name, csv_path, date_cols)
                else:
                    print(f"  Warning: {csv_path} not found, skipping")

            # Reset SERIAL sequences for tables with auto-increment IDs
            print("\nResetting SERIAL sequences...")
            cursor.execute("SELECT MAX(visit_id) FROM visits")
            max_visit_id = cursor.fetchone()[0] or 0
            cursor.execute(f"ALTER SEQUENCE visits_visit_id_seq RESTART WITH {max_visit_id + 1}")
            print(f"  visits_visit_id_seq reset to {max_visit_id + 1}")

            conn.commit()
            cursor.close()
            conn.close()
            print(f"\nTotal rows imported: {total_rows}")

    except Exception as e:
        print(f"Error importing data: {e}")
        raise


def verify_date_types():
    """Verify that visit_date is correctly stored as DATE type."""
    try:
        if 'DBPool' in globals():
            with DBPool.get_connection() as conn:
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
        else:
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
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Could not verify date types: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Clinic AI Assistant - CSV Data Import")
    print("=" * 60)
    print()
    print("Prerequisite: Run init_schema.sql first to create tables")
    print()

    import_all_data()
    verify_date_types()

    print()
    print("Import complete!")
