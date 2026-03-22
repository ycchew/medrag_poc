"""
Import CSV data into Railway PostgreSQL database.

Usage:
    railway run python scripts/import_csv_data_railway.py

Or locally with Railway connection string:
    export DATABASE_URL="your_railway_url"
    python scripts/import_csv_data_railway.py
"""

import os
import sys
import csv
from datetime import datetime
from pathlib import Path

# Add backend to path
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
sys.path.insert(0, str(project_root / "backend"))

import psycopg2
from psycopg2.extras import execute_values

# Get database URL from environment (Railway sets this automatically)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to individual variables
    DATABASE_CONFIG = {
        "host": os.getenv("DATABASE_HOST", "localhost"),
        "port": int(os.getenv("DATABASE_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "clinic_db"),
        "user": os.getenv("POSTGRES_USER", "clinic_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "clinic_password"),
    }
else:
    DATABASE_CONFIG = None

# CSV files location
DATA_DIR = project_root / "data" / "sql"


def parse_date(date_str):
    """Parse date string to date object."""
    if not date_str:
        return None
    formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def import_table_csv(cursor, table_name, csv_path, date_columns=None):
    """Import a CSV file into a database table."""
    print(f"Importing {table_name} from {csv_path}...")
    date_columns = date_columns or []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames

        if not columns:
            raise ValueError(f"No columns found in {csv_path}")

        rows = []
        for row in reader:
            values = []
            for col in columns:
                val = row.get(col)
                if col in date_columns and val:
                    val = parse_date(val)
                values.append(val)
            rows.append(values)

        # Use execute_values for efficient bulk insert
        placeholders = ",".join(["%s"] * len(columns))
        column_names = ",".join(columns)

        insert_query = f"INSERT INTO {table_name} ({column_names}) VALUES %s"
        execute_values(cursor, insert_query, rows, page_size=1000)

    print(f"  Imported {len(rows)} rows into {table_name}")
    return len(rows)


def import_all_data():
    """Import all CSV files into the Railway database."""
    import_order = [
        ("clinics", "clinics.csv", None),
        ("patients", "patients.csv", ["dob"]),
        ("visits", "visits.csv", ["visit_date"]),
        ("diagnoses", "diagnoses.csv", None),
        ("prescriptions", "prescriptions.csv", None),
        ("clinical_notes", "clinical_notes.csv", None),
    ]

    print(f"Looking for CSV files in: {DATA_DIR}")

    # Check CSV files exist
    missing_files = []
    for _, csv_file, _ in import_order:
        csv_path = DATA_DIR / csv_file
        if not csv_path.exists():
            missing_files.append(str(csv_path))

    if missing_files:
        print(f"\nError: Missing required CSV files:")
        for f in missing_files:
            print(f"  - {f}")
        sys.exit(1)

    conn = None
    cursor = None
    try:
        # Connect using DATABASE_URL if available, otherwise use config
        if DATABASE_URL:
            print("Connecting to Railway PostgreSQL using DATABASE_URL...")
            conn = psycopg2.connect(DATABASE_URL)
        else:
            print(f"Connecting to PostgreSQL at {DATABASE_CONFIG['host']}...")
            conn = psycopg2.connect(**DATABASE_CONFIG)

        cursor = conn.cursor()
        print("Connected successfully!")

        total_rows = 0
        for table_name, csv_file, date_cols in import_order:
            csv_path = DATA_DIR / csv_file
            total_rows += import_table_csv(cursor, table_name, str(csv_path), date_cols)

        # Reset SERIAL sequences
        print("\nResetting SERIAL sequences...")
        cursor.execute("SELECT MAX(visit_id) FROM visits")
        max_visit_id = cursor.fetchone()[0] or 0
        cursor.execute(
            f"ALTER SEQUENCE visits_visit_id_seq RESTART WITH {max_visit_id + 1}"
        )
        print(f"  visits_visit_id_seq reset to {max_visit_id + 1}")

        conn.commit()
        print(f"\nTotal rows imported: {total_rows}")
        print("\nDatabase initialization complete!")

    except psycopg2.Error as e:
        print(f"\nDatabase error: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure DATABASE_URL is set correctly")
        print("  2. Verify PostgreSQL is accessible")
        print("  3. Check database credentials")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("\nConnection closed.")


if __name__ == "__main__":
    print("=" * 60)
    print("Clinic AI Assistant - Railway Data Import")
    print("=" * 60)
    print()

    if not DATABASE_URL and not os.getenv("DATABASE_HOST"):
        print("Warning: No database connection found.")
        print("Make sure to set DATABASE_URL or database connection variables.")
        print()
        print("For Railway CLI:")
        print("  railway run python scripts/import_csv_data_railway.py")
        print()
        print("For local with Railway URL:")
        print("  export DATABASE_URL='your_railway_connection_string'")
        print("  python scripts/import_csv_data_railway.py")
        sys.exit(1)

    import_all_data()
