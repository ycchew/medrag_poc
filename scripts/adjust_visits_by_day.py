"""
Script to modify the visits table so that Sunday, Monday, and Friday have 20-30% more visits
than typical weekdays (Tuesday, Wednesday, Thursday).

This script should be run inside the Docker container where the database is accessible.
Usage: python scripts/adjust_visits_by_day.py
"""
import os
import sys
import random
import psycopg2
from datetime import timedelta

# Add backend to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
backend_paths = [
    os.path.join(project_root, "backend"),
    "/app",  # Container path
    ".",  # Current directory
]
for path in backend_paths:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

try:
    from config import DATABASE_CONFIG
except ImportError:
    # Fallback to environment variables
    DATABASE_CONFIG = {
        "host": os.getenv("DATABASE_HOST", "localhost"),
        "port": int(os.getenv("DATABASE_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "clinic_db"),
        "user": os.getenv("POSTGRES_USER", "clinic_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "clinic_password"),
    }


def adjust_visits_by_day():
    """Increase Sunday, Monday, and Friday visits by 20-30% over typical weekdays."""
    conn = psycopg2.connect(**DATABASE_CONFIG)
    conn.autocommit = True
    cursor = conn.cursor()

    try:
        # First, let's analyze current data
        cursor.execute("""
            SELECT EXTRACT(DOW FROM visit_date) as day_num,
                   COUNT(*) as visit_count
            FROM visits
            GROUP BY EXTRACT(DOW FROM visit_date)
            ORDER BY day_num
        """)
        results = cursor.fetchall()

        print("Current visits by day of week:")
        day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        current_counts = {}
        for row in results:
            day_num, count = row
            current_counts[int(day_num)] = count
            print(f"  {day_names[int(day_num)]:9s}: {count}")

        # Calculate average visits for typical weekdays (Tuesday, Wednesday, Thursday)
        typical_days = [2, 3, 4]  # Tuesday, Wednesday, Thursday
        typical_counts = [current_counts.get(d, 0) for d in typical_days]
        avg_typical = sum(typical_counts) / len(typical_counts) if typical_counts else 0

        print(f"\nAverage typical weekday visits (Tue-Thu): {avg_typical:.0f}")

        # Target: Sunday, Monday, Friday should be 20-30% higher than typical weekdays
        min_boost, max_boost = 1.20, 1.30

        # Calculate target counts for each boost day
        targets = {}
        for day in [0, 1, 5]:  # Sunday, Monday, Friday
            targets[day] = int(avg_typical * random.uniform(min_boost, max_boost))

        print(f"\nTarget visits (20-30% boost over {avg_typical:.0f}):")
        for day in [0, 1, 5]:
            print(f"  {day_names[day]:9s}: ~{targets[day]}")

        # Boost days to process: Sunday (0), Monday (1), Friday (5)
        boost_days = [
            (0, "Sunday"),
            (1, "Monday"),
            (5, "Friday")
        ]

        for day_num, day_name in boost_days:
            current_count = current_counts.get(day_num, 0)
            target_count = targets[day_num]
            needed = target_count - current_count

            print(f"\nCurrent {day_name} visits: {current_count}")
            print(f"Target {day_name} visits: ~{target_count}")

            if needed <= 0:
                print(f"  No visits needed for {day_name} (already at target)")
                continue

            print(f"  Adding {needed} visits for {day_name}...")

            # Get visits from typical weekdays to copy
            cursor.execute("""
                SELECT v.visit_id, v.patient_id, v.clinic_id, v.visit_date
                FROM visits v
                WHERE EXTRACT(DOW FROM v.visit_date) IN %s
                ORDER BY RANDOM()
                LIMIT %s
            """, (tuple(typical_days), needed))

            visits_to_copy = cursor.fetchall()

            for visit_id, patient_id, clinic_id, visit_date in visits_to_copy:
                # Calculate days to shift to target day
                # visit_date.isoweekday(): Monday=1, Sunday=7
                current_iso_dow = visit_date.isoweekday()  # 1-7

                # Convert target day_num to iso weekday
                # day_num: Sunday=0, Monday=1, ..., Saturday=6
                if day_num == 0:  # Sunday
                    target_iso_dow = 7
                else:
                    target_iso_dow = day_num  # Monday=1, Friday=5

                days_to_shift = (target_iso_dow - current_iso_dow) % 7
                new_date = visit_date + timedelta(days=days_to_shift)

                cursor.execute("""
                    INSERT INTO visits (patient_id, clinic_id, visit_date)
                    VALUES (%s, %s, %s)
                """, (patient_id, clinic_id, new_date))

            print(f"  Added {len(visits_to_copy)} visits for {day_name}.")

        # Verify final results
        print("\nFinal visits by day of week:")
        cursor.execute("""
            SELECT EXTRACT(DOW FROM visit_date) as day_num,
                   COUNT(*) as visit_count
            FROM visits
            GROUP BY EXTRACT(DOW FROM visit_date)
            ORDER BY day_num
        """)
        results = cursor.fetchall()

        final_counts = {}
        for row in results:
            day_num, count = row
            final_counts[int(day_num)] = count
            marker = ""
            if int(day_num) in [0, 1, 5]:  # Boost days
                marker = "* (boosted)"
            print(f"  {day_names[int(day_num)]:9s}: {count} {marker}")

        # Show boost percentages
        print("\nBoost percentages (compared to typical weekday average):")
        avg_typical_final = sum([final_counts.get(d, 0) for d in typical_days]) / len(typical_days)
        for day_num, day_name in boost_days:
            count = final_counts.get(day_num, 0)
            boost_pct = ((count / avg_typical_final) - 1) * 100 if avg_typical_final > 0 else 0
            print(f"  {day_name:9s}: {boost_pct:+.1f}%")

        print("\nDone!")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    adjust_visits_by_day()
