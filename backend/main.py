"""
FastAPI Application - Main entry point for the Clinic AI Assistant API.
"""

import time
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Literal, Dict, Any

from config import LLM_API_KEY
from database import init_db, DBPool
from services.query_router import classify_query, save_chat_message, get_query_history
from services.rag_service import (
    vector_search,
    hybrid_search,
    format_retrieved_chunks_for_prompt,
)
from services.text_to_sql import text_to_sql
from services.dashboard_service import (
    get_dashboard_stats,
    get_visits_by_day,
    get_trending_diseases,
    get_all_dashboard_data,
)
from prompts import CLINICAL_KNOWLEDGE_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
init_db()

# Import llm_client for health check
from services.llm_client import llm_client

# Create FastAPI app
app = FastAPI(
    title="Clinic AI Assistant API",
    description="API for the Clinic AI Assistant - Clinical Knowledge Q&A and Patient Data Analysis",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


# Request/Response Models
class QueryRequest(BaseModel):
    question: str
    session_id: str = "default_session"


class ChatMessage(BaseModel):
    session_id: str
    user_message: str
    ai_response: str
    query_type: str


class QueryResponse(BaseModel):
    question: str
    classification: str
    response: str
    source_documents: Optional[List[str]] = None
    source_chunks: Optional[List[Dict[str, Any]]] = None
    sql_query: Optional[str] = None


# Health Check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {"database": True, "llm": bool(LLM_API_KEY)},
    }


# Dashboard Endpoints
@app.get("/dashboard/stats")
async def get_stats():
    return get_dashboard_stats()


@app.get("/dashboard/visits-by-day")
async def get_visits_by_day_data():
    return get_visits_by_day()


@app.get("/dashboard/trending-diseases")
async def get_trending_diseases_data():
    return get_trending_diseases()


@app.get("/dashboard/all")
async def get_all_dashboard():
    """Get all dashboard data in a single request."""
    return get_all_dashboard_data()


# Query Classification
@app.post("/classify")
async def classify(question: str):
    return {"classification": classify_query(question)}


# RAG Endpoint
@app.post("/rag")
async def rag_query(request: QueryRequest):
    """Process a document query (RAG pipeline)."""
    from services.llm_client import llm_client

    total_start = time.time()

    # Classify the query
    t0 = time.time()
    query_type = classify_query(request.question)
    t1 = time.time()
    logger.info(f"[TIMING] Query classification: {t1 - t0:.3f}s")

    if query_type != "DOCUMENT_QUERY":
        return {
            "classification": query_type,
            "response": "This question is better answered through patient data queries. Please ask about clinic statistics or specific patient history.",
            "source_documents": [],
            "sql_query": None,
        }

    # Perform hybrid search (BM25 + Vector)
    t0 = time.time()
    chunks = hybrid_search(request.question, top_k=5, bm25_weight=0.3)
    t1 = time.time()
    logger.info(f"[TIMING] Hybrid search: {t1 - t0:.3f}s")

    if not chunks:
        return {
            "classification": query_type,
            "response": "I could not find any relevant information in the clinic documents. Please try rephrasing your question or ask about clinic statistics.",
            "source_documents": [],
            "sql_query": None,
        }

    # Format chunks for prompt
    t0 = time.time()
    retrieved_chunks = format_retrieved_chunks_for_prompt(chunks)
    t1 = time.time()
    logger.info(f"[TIMING] Format chunks: {t1 - t0:.3f}s")

    # Generate response using LLM
    t0 = time.time()
    prompt = CLINICAL_KNOWLEDGE_PROMPT.format(
        retrieved_chunks=retrieved_chunks, user_question=request.question
    )

    response = llm_client.generate(
        system_prompt="You are a clinical knowledge assistant for a clinic group. Answer using ONLY the provided context. Be concise.",
        user_prompt=prompt,
        max_tokens=256,  # Reduced from 512 for faster responses
    )
    t1 = time.time()
    logger.info(f"[TIMING] LLM generation: {t1 - t0:.3f}s")

    # Extract document names and full chunks for sources
    sources = list(set([c["source_file"] for c in chunks]))
    source_chunks = [
        {
            "document_name": c["document_name"],
            "source_file": c["source_file"],
            "content": c["content"][:500] + "..."
            if len(c["content"]) > 500
            else c["content"],
            "similarity": round(c["similarity"], 3),
        }
        for c in chunks
    ]

    total_time = time.time() - total_start
    logger.info(f"[TIMING] Total RAG query: {total_time:.3f}s")

    return {
        "classification": query_type,
        "response": response,
        "source_documents": sources,
        "source_chunks": source_chunks,
        "sql_query": None,
    }


# Text-to-SQL Endpoint
@app.post("/sql-query")
async def sql_query_endpoint(request: QueryRequest):
    """Process a SQL query (patient data/statistics)."""
    # Classify the query
    query_type = classify_query(request.question)

    if query_type != "SQL_QUERY":
        return {
            "classification": query_type,
            "response": "This question is better answered through clinical knowledge lookup. Please ask about treatment guidelines or medical information.",
            "source_documents": None,
            "sql_query": None,
        }

    # Execute Text-to-SQL
    result = text_to_sql(request.question)

    if not result["success"]:
        return {
            "classification": query_type,
            "response": f"Sorry, I encountered an error processing your query: {result.get('error', 'Unknown error')}",
            "source_documents": None,
            "sql_query": result.get("sql_query"),
        }

    # Save to chat history
    save_chat_message(
        session_id=request.session_id,
        user_message=request.question,
        ai_response=result["natural_language_response"],
        query_type=query_type,
    )

    return {
        "classification": query_type,
        "response": result["natural_language_response"],
        "source_documents": None,
        "sql_query": result["sql_query"],
    }


# Chat History Endpoint
@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get chat history for a session."""
    history = get_query_history(session_id)
    return {"session_id": session_id, "history": history}


# General Chat Endpoint (handles both query types)
@app.post("/chat", response_model=QueryResponse)
async def chat(request: QueryRequest):
    """Main chat endpoint that auto-routes to RAG or SQL based on query type."""
    # Classify
    query_type = classify_query(request.question)

    if query_type == "DOCUMENT_QUERY":
        # RAG pipeline
        from services.llm_client import llm_client

        chunks = hybrid_search(request.question, top_k=5, bm25_weight=0.3)

        if not chunks:
            response = (
                "I could not find any relevant information in the clinic documents."
            )
            sources = []
            source_chunks = []
        else:
            retrieved_chunks = format_retrieved_chunks_for_prompt(chunks)
            sources = list(set([c["source_file"] for c in chunks]))
            source_chunks = [
                {
                    "document_name": c["document_name"],
                    "source_file": c["source_file"],
                    "content": c["content"][:500] + "..."
                    if len(c["content"]) > 500
                    else c["content"],
                    "similarity": round(c["similarity"], 3),
                }
                for c in chunks
            ]

            # Generate response using LLM
            prompt = CLINICAL_KNOWLEDGE_PROMPT.format(
                retrieved_chunks=retrieved_chunks, user_question=request.question
            )

            response = llm_client.generate(
                system_prompt="You are a clinical knowledge assistant for a clinic group. Answer using ONLY the provided context.",
                user_prompt=prompt,
            )

        return QueryResponse(
            question=request.question,
            classification=query_type,
            response=response,
            source_documents=sources,
            source_chunks=source_chunks,
            sql_query=None,
        )

    else:
        # SQL pipeline
        result = text_to_sql(request.question)

        if not result["success"]:
            response = (
                f"Sorry, I encountered an error: {result.get('error', 'Unknown error')}"
            )
            return QueryResponse(
                question=request.question,
                classification=query_type,
                response=response,
                source_documents=None,
                sql_query=result.get("sql_query"),
            )

        save_chat_message(
            session_id=request.session_id,
            user_message=request.question,
            ai_response=result["natural_language_response"],
            query_type=query_type,
        )

        return QueryResponse(
            question=request.question,
            classification=query_type,
            response=result["natural_language_response"],
            source_documents=None,
            sql_query=result["sql_query"],
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
