"""
Dashboard Data Service - Provides data for clinic statistics and charts.
"""
from typing import List, Dict, Any
from database import DBPool
from datetime import datetime, timedelta


def get_dashboard_stats() -> Dict[str, Any]:
    """Get summary statistics for the dashboard."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        # Total clinics
        cursor.execute("SELECT COUNT(*) FROM clinics")
        total_clinics = cursor.fetchone()[0]

        # Total patients
        cursor.execute("SELECT COUNT(*) FROM patients")
        total_patients = cursor.fetchone()[0]

        # Total visits
        cursor.execute("SELECT COUNT(*) FROM visits")
        total_visits = cursor.fetchone()[0]

        # Today's patients (unique patients with visits today)
        cursor.execute("""
            SELECT COUNT(DISTINCT p.patient_id)
            FROM patients p
            JOIN visits v ON p.patient_id = v.patient_id
            WHERE v.visit_date = CURRENT_DATE
        """)
        today_patients = cursor.fetchone()[0]

        # Today's visits
        cursor.execute("SELECT COUNT(*) FROM visits WHERE visit_date = CURRENT_DATE")
        today_visits = cursor.fetchone()[0]

        return {
            "total_clinics": total_clinics,
            "total_patients": total_patients,
            "total_visits": total_visits,
            "today_patients": today_patients,
            "today_visits": today_visits
        }


def get_visits_by_day() -> List[Dict[str, Any]]:
    """Get visit counts by day of week."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TO_CHAR(v.visit_date, 'Day') as day_name,
                   EXTRACT(DOW FROM v.visit_date) as day_num,
                   COUNT(*) as visit_count
            FROM visits v
            GROUP BY TO_CHAR(v.visit_date, 'Day'), EXTRACT(DOW FROM v.visit_date)
            ORDER BY day_num
        """)

        results = cursor.fetchall()
        return [{"day": row[0].strip(), "count": row[2]} for row in results]


def get_trending_diseases() -> Dict[str, Any]:
    """Get disease counts by day of week for all diseases."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT d.description as disease,
                   EXTRACT(DOW FROM v.visit_date) as day_num,
                   TO_CHAR(v.visit_date, 'Day') as day_name,
                   COUNT(*) as count
            FROM diagnoses d
            JOIN visits v ON d.visit_id = v.visit_id
            GROUP BY d.description, EXTRACT(DOW FROM v.visit_date), TO_CHAR(v.visit_date, 'Day')
            ORDER BY day_num, count DESC
        """)

        rows = cursor.fetchall()

        # Organize data: days are labels, each disease is a dataset
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        diseases = []
        data = {day: {} for day in days}

        for row in rows:
            disease, day_num, day_name, count = row
            if disease not in diseases:
                diseases.append(disease)
            data[day_name.strip()][disease] = count

        return {
            "days": days,
            "diseases": diseases,
            "data": data
        }


def get_recent_visits(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent visits with patient and clinic info."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT v.visit_id, v.visit_date, p.name, c.clinic_name, d.description
            FROM visits v
            JOIN patients p ON v.patient_id = p.patient_id
            JOIN clinics c ON v.clinic_id = c.clinic_id
            JOIN diagnoses d ON v.visit_id = d.visit_id
            ORDER BY v.visit_date DESC
            LIMIT %s
        """, (limit,))

        rows = cursor.fetchall()
        return [
            {
                "visit_id": row[0],
                "visit_date": str(row[1]),
                "patient_name": row[2],
                "clinic": row[3],
                "diagnosis": row[4]
            }
            for row in rows
        ]


def get_clinic_summary() -> List[Dict[str, Any]]:
    """Get summary of clinic statistics."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.clinic_name,
                   COUNT(DISTINCT v.visit_id) as total_visits,
                   COUNT(DISTINCT p.patient_id) as total_patients,
                   COUNT(DISTINCT CASE WHEN v.visit_date = CURRENT_DATE THEN v.visit_id END) as today_visits
            FROM clinics c
            LEFT JOIN visits v ON c.clinic_id = v.clinic_id
            LEFT JOIN patients p ON v.patient_id = p.patient_id
            GROUP BY c.clinic_name
            ORDER BY total_visits DESC
        """)

        rows = cursor.fetchall()
        return [
            {
                "clinic_name": row[0],
                "total_visits": row[1],
                "total_patients": row[2],
                "today_visits": row[3]
            }
            for row in rows
        ]


def get_all_dashboard_data() -> Dict[str, Any]:
    """Get all dashboard data in a single database transaction."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        # Get all stats in one go
        cursor.execute("SELECT COUNT(*) FROM clinics")
        total_clinics = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM patients")
        total_patients = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM visits")
        total_visits = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT p.patient_id)
            FROM patients p
            JOIN visits v ON p.patient_id = v.patient_id
            WHERE v.visit_date = CURRENT_DATE
        """)
        today_patients = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM visits WHERE visit_date = CURRENT_DATE")
        today_visits = cursor.fetchone()[0]

        stats = {
            "total_clinics": total_clinics,
            "total_patients": total_patients,
            "total_visits": total_visits,
            "today_patients": today_patients,
            "today_visits": today_visits
        }

        # Get visits by day
        cursor.execute("""
            SELECT TO_CHAR(v.visit_date, 'Day') as day_name,
                   EXTRACT(DOW FROM v.visit_date) as day_num,
                   COUNT(*) as visit_count
            FROM visits v
            GROUP BY TO_CHAR(v.visit_date, 'Day'), EXTRACT(DOW FROM v.visit_date)
            ORDER BY day_num
        """)
        visits_by_day = [{"day": row[0].strip(), "count": row[2]} for row in cursor.fetchall()]

        # Get trending diseases
        cursor.execute("""
            SELECT d.description as disease,
                   EXTRACT(DOW FROM v.visit_date) as day_num,
                   TO_CHAR(v.visit_date, 'Day') as day_name,
                   COUNT(*) as count
            FROM diagnoses d
            JOIN visits v ON d.visit_id = v.visit_id
            GROUP BY d.description, EXTRACT(DOW FROM v.visit_date), TO_CHAR(v.visit_date, 'Day')
            ORDER BY day_num, count DESC
        """)

        rows = cursor.fetchall()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        diseases = []
        data = {day: {} for day in days}

        for row in rows:
            disease, day_num, day_name, count = row
            if disease not in diseases:
                diseases.append(disease)
            data[day_name.strip()][disease] = count

        trending_diseases = {
            "days": days,
            "diseases": diseases,
            "data": data
        }

        return {
            "stats": stats,
            "visits_by_day": visits_by_day,
            "trending_diseases": trending_diseases
        }
