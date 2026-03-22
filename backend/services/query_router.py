"""
Query Router Service - Classifies questions into DOCUMENT_QUERY or SQL_QUERY.
"""
from functools import lru_cache
from typing import Literal
from services.llm_client import llm_client
from prompts import QUERY_CLASSIFICATION_PROMPT
from database import DBPool


# Cache classification results for common queries
@lru_cache(maxsize=100)
def classify_query(user_question: str) -> Literal["DOCUMENT_QUERY", "SQL_QUERY"]:
    """
    Classify a user's question into either DOCUMENT_QUERY or SQL_QUERY.

    Uses fast keyword-based detection first, only falling back to LLM
    if the classification is ambiguous.

    Returns:
        "DOCUMENT_QUERY" - for medical knowledge, treatment guidelines, clinic policies
        "SQL_QUERY" - for statistics, patient counts, clinic activity
    """
    # First try fast keyword-based classification
    result = detect_query_type(user_question)

    # Only use LLM for ambiguous cases (no clear keywords matched)
    # This saves 7+ seconds per query
    question_lower = user_question.lower()
    sql_keywords = [
        "how many", "count", "total", "number of", "statistics", "trend",
        "which clinic", "recent", "last month", "this week", "percentage",
        "average", "ratio", "compare", "most", "least", "highest", "lowest"
    ]
    document_keywords = [
        "treatment", "guideline", "protocol", "medication", "diagnosis",
        "symptom", "causes", "risk factor", "management", "recommendation",
        "what is", "what are", "how to", "explain"
    ]

    has_sql_kw = any(kw in question_lower for kw in sql_keywords)
    has_doc_kw = any(kw in question_lower for kw in document_keywords)

    # If we have clear keyword matches, use the fast result
    if has_sql_kw or has_doc_kw:
        return result

    # Ambiguous case - fall back to LLM classification
    prompt = QUERY_CLASSIFICATION_PROMPT.format(user_question=user_question)
    response = llm_client.generate(
        system_prompt="You are a query classification assistant. Return only DOCUMENT_QUERY or SQL_QUERY.",
        user_prompt=prompt,
        max_tokens=10  # Keep it short and fast
    )

    classification = response.strip().upper()
    if "DOCUMENT" in classification:
        return "DOCUMENT_QUERY"
    elif "SQL" in classification:
        return "SQL_QUERY"
    else:
        return result


def detect_query_type(question: str) -> Literal["DOCUMENT_QUERY", "SQL_QUERY"]:
    """
    Fallback query type detection based on question keywords.
    """
    sql_keywords = [
        "how many", "count", "total", "number of", "statistics", "trend",
        "which clinic", "recent", "last month", "this week", "percentage",
        "average", "ratio", "compare"
    ]

    document_keywords = [
        "treatment", "guideline", "protocol", "medication", "diagnosis",
        "symptom", "causes", "risk factor", "management", "recommendation"
    ]

    question_lower = question.lower()

    sql_count = sum(1 for kw in sql_keywords if kw in question_lower)
    doc_count = sum(1 for kw in document_keywords if kw in question_lower)

    if sql_count >= doc_count:
        return "SQL_QUERY"
    else:
        return "DOCUMENT_QUERY"


def get_query_history(session_id: str) -> list:
    """Get chat history for a session."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_message, ai_response, query_type, timestamp
            FROM chat_sessions
            WHERE session_id = %s
            ORDER BY timestamp DESC
            LIMIT 20
        """, (session_id,))
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "user_message": row[1],
                "ai_response": row[2],
                "query_type": row[3],
                "timestamp": row[4].isoformat() if row[4] else None
            }
            for row in rows
        ]


def save_chat_message(
    session_id: str,
    user_message: str,
    ai_response: str,
    query_type: str
):
    """Save a chat message to the database."""
    with DBPool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_sessions (session_id, user_message, ai_response, query_type)
            VALUES (%s, %s, %s, %s)
        """, (session_id, user_message, ai_response, query_type))


if __name__ == "__main__":
    # Test classification
    test_questions = [
        "What is the treatment for hypertension?",
        "How many diabetic patients visited last month?",
        "Which clinic has the most dengue cases?"
    ]

    for q in test_questions:
        result = classify_query(q)
        print(f"Question: {q}")
        print(f"Classification: {result}")
        print("---")
