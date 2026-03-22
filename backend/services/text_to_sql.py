"""
Text-to-SQL Service - Generates and executes SQL queries against clinic database.
"""
from typing import List, Dict, Any
from services.llm_client import llm_client
from database import DBPool
from prompts import SQL_GENERATION_PROMPT, SQL_EXPLANATION_PROMPT


# Get database schema as a string
DATABASE_SCHEMA = """
Database Schema:

1. clinics
   - clinic_id (INTEGER, PK)
   - clinic_name (VARCHAR)
   - location (VARCHAR)

2. patients
   - patient_id (INTEGER, PK)
   - name (VARCHAR)
   - dob (DATE)
   - gender (VARCHAR)

3. visits
   - visit_id (INTEGER, PK)
   - patient_id (INTEGER, FK -> patients)
   - clinic_id (INTEGER, FK -> clinics)
   - visit_date (DATE)

4. diagnoses
   - diagnosis_id (INTEGER, PK)
   - visit_id (INTEGER, FK -> visits)
   - icd_code (VARCHAR)
   - description (VARCHAR)

5. prescriptions
   - prescription_id (INTEGER, PK)
   - visit_id (INTEGER, FK -> visits)
   - drug_name (VARCHAR)
   - dosage (VARCHAR)

6. clinical_notes
   - note_id (INTEGER, PK)
   - visit_id (INTEGER, FK -> visits)
   - diagnosis (VARCHAR)
   - clinical_note (TEXT)
"""


def generate_sql_query(question: str, schema: str = DATABASE_SCHEMA) -> str:
    """Generate SQL query from natural language question."""
    prompt = SQL_GENERATION_PROMPT.format(database_schema=schema, user_question=question)

    # Extract only the SQL query from the response
    response = llm_client.generate(
        system_prompt="You are a SQL query generator. Return only the SQL query.",
        user_prompt=prompt
    )

    # Extract SQL from response (remove markdown code blocks and extra text)
    sql = response.strip()
    if sql.startswith('```sql'):
        sql = sql[6:]
    if sql.startswith('```'):
        sql = sql[3:]
    if sql.endswith('```'):
        sql = sql[:-3]

    sql = sql.strip()

    # Ensure LIMIT 100 is present for safety (remove existing first to avoid duplicates)
    # The prompt says "Always append LIMIT 100" but the LLM sometimes includes it
    sql_lower = sql.lower()
    if "limit" in sql_lower:
        # Remove any existing LIMIT clause to avoid duplicates
        import re
        sql = re.sub(r'\s+limit\s*\d+\s*;?\s*$', '', sql, flags=re.IGNORECASE)
    sql += " LIMIT 100;"

    return sql


def execute_sql_query(sql: str) -> List[Dict[str, Any]]:
    """Execute SQL query and return results as list of dictionaries."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()

        # Execute the query
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        # Convert to list of dictionaries
        results = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                row_dict[col] = str(value) if isinstance(value, (bytes, bytearray)) else value
            results.append(row_dict)

        return results


def explain_sql_result(question: str, sql: str, result: List[Dict[str, Any]]) -> str:
    """Natural language explanation of SQL query results with markdown formatting."""
    result_str = str(result[:20])  # Limit result display
    if len(result) > 20:
        result_str = result_str[:-1] + f"... ({len(result)} total rows)"

    prompt = SQL_EXPLANATION_PROMPT.format(
        user_question=question,
        sql_result=result_str
    )

    response = llm_client.generate(
        system_prompt="You are a clinic data assistant. Provide clear, concise natural language explanations using Markdown formatting. Use **bold** for important numbers and clinic names.",
        user_prompt=prompt
    )

    return response


def text_to_sql(question: str) -> Dict[str, Any]:
    """
    Complete Text-to-SQL pipeline:
    1. Generate SQL query from question
    2. Execute the query
    3. Explain the results in natural language

    Returns dict with sql_query, raw_results, and natural_language_response.
    """
    # Generate SQL
    sql_query = generate_sql_query(question)

    # Execute
    try:
        raw_results = execute_sql_query(sql_query)
    except Exception as e:
        return {
            "success": False,
            "error": f"Query execution error: {str(e)}",
            "sql_query": sql_query
        }

    # Explain
    natural_language = explain_sql_result(question, sql_query, raw_results)

    return {
        "success": True,
        "sql_query": sql_query,
        "raw_results": raw_results,
        "natural_language_response": natural_language
    }


if __name__ == "__main__":
    # Test Text-to-SQL
    test_questions = [
        "How many diabetic patients visited last month?",
        "What is the total number of clinics?",
        "Which clinic has the most visits?"
    ]

    for q in test_questions:
        print(f"\nQuestion: {q}")
        result = text_to_sql(q)
        print(f"SQL: {result.get('sql_query', 'N/A')}")
        print(f"Response: {result.get('natural_language_response', 'N/A')[:200]}...")
