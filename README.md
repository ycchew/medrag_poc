# Clinic AI Assistant

A Proof of Concept (PoC) RAG chatbot for a clinic group database. **Based on real-world clinical requirements**, this demo uses **synthetic patient data** to demonstrate AI-powered clinical assistants that allow doctors to ask natural language questions about clinic guidelines (via RAG) and clinic statistics/patient histories (via Text-to-SQL).

> **Note**: This PoC uses realistic but entirely synthetic patient data for demonstration purposes. All patient names, IDs, and clinical records are computer-generated and do not represent real individuals.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend  │────▶│   Backend    │────▶│   Database   │
│  (Nginx)    │     │  (FastAPI)   │     │ (PostgreSQL) │
└─────────────┘     └──────────────┘     └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    LLM API   │
                    │ (Qwen3.5+)   │
                    └──────────────┘
```

## Quick Start

### Data Privacy Notice
This demo uses **synthetic patient data** - all records are computer-generated for demonstration purposes. No real patient information is used.

### Prerequisites
- Docker and Docker Compose installed
- LLM API key (Qwen3.5 Plus or OpenAI)

### Setup

1. **Start containers and run initialization**
   ```bash
   docker compose up -d --build
   echo "y" | docker exec -i clinic_backend python scripts/init-me.py
   # after finished setup, restart the containers
   export LLM_API_KEY=<the key>
   docker compose down
   docker compose up -d --build
   ```

2. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000/docs (Swagger)

## Project Structure

```
.
├── backend/              # FastAPI application
│   ├── main.py          # API entry point
│   ├── database.py      # DB connection + schema init
│   └── services/
│       ├── llm_client.py       # LLM API integration
│       ├── rag_service.py      # RAG (chunking, embeddings, search)
│       ├── query_router.py     # Query classification
│       ├── text_to_sql.py      # SQL generation & execution
│       └── dashboard_service.py # Statistics & charts
├── frontend/            # Static HTML + Tailwind CSS
├── data/
│   ├── docs/           # Medical guidelines (ingested into RAG)
│   └── sql/            # Synthetic clinic data (CSV files) - computer-generated for demo
├── scripts/            # Setup and ingestion scripts
│   ├── init-me.py      # One-command initialization
│   ├── import_csv_data.py
│   ├── ingest_documents.py
│   └── migrate_bm25.py
├── docker-compose.yml
└── .env
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /chat | Auto-routed query (RAG or SQL) |
| POST | /rag | Document query only |
| POST | /sql-query | Patient data query only |
| POST | /classify | Classify query type |
| GET | /dashboard/all | All dashboard data |
| GET | /history/{session_id} | Chat history |

## Demo Scenarios

1. **Clinical Knowledge (RAG)**
   - "What is the treatment for hypertension?"
   - "What are the first-line medications for asthma?"

2. **Clinic Statistics (SQL)**
   - "How many diabetic patients visited last month?"
   - "Which clinic has the most dengue cases?"

## Docker Compose Services

| Service | Port | Description |
|---------|------|-------------|
| db | 5432 | PostgreSQL + pgvector |
| backend | 8000 | FastAPI application |
| frontend | 3000 | Nginx serving static HTML |
