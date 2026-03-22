# Clinic AI Assistant - Dev Plan

## Architecture

**Hybrid RAG + Text-to-SQL System**
- Query Router classifies questions as `DOCUMENT_QUERY` (RAG) or `SQL_QUERY` (Text-to-SQL)
- Strict data partitioning: Vector store for guidelines, relational tables for patient data
- Cloud LLM (Qwen3.5 Plus) with local embeddings (all-MiniLM-L6-v2, 384-dim)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Static HTML + Tailwind CSS served via Nginx |
| Backend | FastAPI (Python 3.11) |
| Database | PostgreSQL 16 + pgvector |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| LLM | Qwen3.5 Plus via DashScope API |

## Database Schema

**Relational Tables (synthetic clinic data)**
- `clinics`: clinic_id (PK), clinic_name, location
- `patients`: patient_id (PK), name, dob (DATE), gender
- `visits`: visit_id (PK), patient_id (FK), clinic_id (FK), visit_date (DATE)
- `diagnoses`: diagnosis_id (PK), visit_id (FK), icd_code, description
- `prescriptions`: prescription_id (PK), visit_id (FK), drug_name, dosage
- `clinical_notes`: note_id (PK), visit_id (FK), diagnosis, clinical_note (TEXT)

**Vector Store**
- `document_chunks`: id, document_name, content, embedding (vector(384)), source_file, content_tsv (TSVECTOR)
- Indexes: HNSW (cosine), GIN (full-text), triggers for auto TSV update

**Chat History**
- `chat_sessions`: session_id, user_message, ai_response, query_type, timestamp

## Backend Services

**llm_client.py**
- Claude-compatible API client for Qwen3.5 Plus
- Local embedding model (all-MiniLM-L6-v2)
- Methods: `generate()`, `embed()`, `generate_with_stream()`

**query_router.py**
- Fast keyword-based classification (SQL vs Document keywords)
- LLM fallback for ambiguous queries with LRU caching
- Chat history persistence

**rag_service.py**
- Document chunking: 2000 chars with 200 overlap, sentence boundary preservation
- Hybrid search: BM25 (GIN index) + Vector (HNSW) with configurable weighting
- Chunk formatting with source attribution

**text_to_sql.py**
- Schema-constrained SQL generation with LIMIT 100 enforcement
- Raw result to natural language explanation via LLM
- Read-only execution safety

**dashboard_service.py**
- Stats, visits-by-day, trending-diseases aggregations
- Single-transaction endpoint for dashboard data

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/chat` | Main entry - auto-routes to RAG or SQL |
| `/rag` | Document query only |
| `/sql-query` | Patient data query only |
| `/classify` | Query type classification |
| `/history/{session_id}` | Chat history retrieval |
| `/dashboard/all` | Dashboard data (stats, charts) |
| `/health` | Service health check |

## Prompts (backend/prompts.py)

1. **QUERY_CLASSIFICATION_PROMPT**: Routes to DOCUMENT_QUERY or SQL_QUERY
2. **CLINICAL_KNOWLEDGE_PROMPT**: RAG response using retrieved context only
3. **SQL_GENERATION_PROMPT**: Schema-bound SELECT with LIMIT 100 rule
4. **SQL_EXPLANATION_PROMPT**: Natural language summary of SQL results

## Query Classification Logic

**Fast Path (Keyword Detection)**
- SQL keywords: "how many", "count", "total", "statistics", "which clinic", "last month", "average", "ratio"
- Document keywords: "treatment", "guideline", "protocol", "medication", "diagnosis", "symptom", "what is"

**Fallback Path**
- LLM classification only when keywords are ambiguous
- Cached results (LRU, maxsize=100)

## RAG Pipeline

1. Generate query embedding (local model)
2. Hybrid search: BM25 score * weight + Vector score * (1 - weight)
3. Format top 5 chunks with source attribution
4. LLM generates response using context only

## Text-to-SQL Pipeline

1. Generate SQL using schema-constrained prompt
2. Enforce LIMIT 100 (regex removal of existing LIMIT + append)
3. Execute against read-only connection
4. LLM explains results in natural language

## Safety Controls

- SQL: SELECT-only, LIMIT 100 enforced, read-only DB user
- RAG: Context-only responses, "I cannot find the answer" fallback
- No patient PII in vector store (strict partition)

## Docker Services

- `db`: pgvector/pgvector:pg16 (port 5432)
- `backend`: FastAPI with hot reload (port 8000)
- `frontend`: Nginx serving static HTML (port 3000)

## Environment Variables

```
POSTGRES_USER=clinic_user
POSTGRES_PASSWORD=clinic_password
POSTGRES_DB=clinic_db
LLM_MODEL=qwen3.5-plus
LLM_API_URL=https://coding-intl.dashscope.aliyuncs.com
```

## Testing Commands

```bash
# Test query classification
curl -X POST "http://localhost:8000/classify" -d "question=How many diabetic patients?"

# Test RAG query
curl -X POST "http://localhost:8000/rag" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the treatment for hypertension?"}'

# Test SQL query
curl -X POST "http://localhost:8000/sql-query" \
  -H "Content-Type: application/json" \
  -d '{"question":"How many visits today?"}'

# Test chat (auto-routed)
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the treatment for hypertension?"}'
```
