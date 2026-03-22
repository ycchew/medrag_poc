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

### Deployment Options

| Option | Best For | Setup Time |
|--------|----------|------------|
| **Railway** (Recommended) | Free cloud hosting, easy setup | 10 min |
| **Docker** | Local development, full control | 15 min |
| **Local** | Existing PostgreSQL database | 20 min |

### Prerequisites
- LLM API key (Qwen3.5 Plus or OpenAI)
- GitHub account (for Railway)

---

## Option 1: Railway Deployment (Free Cloud Hosting)

Railway offers free tier hosting with PostgreSQL + pgvector included.

### 1. Fork and Connect

1. Fork this repository on GitHub
2. Create a free account at [Railway](https://railway.app/)
3. Create new project → "Deploy from GitHub repo"
4. Select your forked repository

### 2. Add PostgreSQL Database

1. In Railway project, click **"New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway automatically enables pgvector

### 3. Configure Environment Variables

In your app service **Variables** tab, add:

| Variable | Value | Source |
|----------|-------|--------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Reference |
| `LLM_API_KEY` | `your_api_key` | Direct |
| `LLM_API_URL` | `https://coding-intl.dashscope.aliyuncs.com` | Direct |
| `LLM_MODEL` | `qwen3.5-plus` | Direct |

### 4. Deploy

Railway automatically deploys on push. Access your app at:
- `https://your-app-name.up.railway.app/` - Frontend
- `https://your-app-name.up.railway.app/health` - Health check

### 5. Initialize Database (One-time)

Use Railway CLI or Web Shell:

```bash
# Using Railway CLI
railway login
railway link
railway run python scripts/import_csv_data_railway.py
railway run python scripts/ingest_documents_railway.py
```

Or via Web Shell in Railway dashboard:
1. Go to your app service → **"Shell"** tab
2. Run: `python scripts/import_csv_data_railway.py`
3. Run: `python scripts/ingest_documents_railway.py`

---

## Option 2: Docker (Local Development)

## Project Structure

```
.
├── backend/              # FastAPI application
│   ├── main.py          # API entry point
│   ├── database.py      # DB connection + schema init
│   ├── config.py        # Environment configuration
│   ├── requirements.txt # Python dependencies
│   ├── requirements.railway.txt # Slim deps for Railway
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
│   ├── init-me.py      # One-command initialization (Docker)
│   ├── import_csv_data.py      # Docker version
│   ├── import_csv_data_local.py    # Local PostgreSQL
│   ├── import_csv_data_railway.py  # Railway PostgreSQL
│   ├── ingest_documents.py       # Docker version
│   ├── ingest_documents_local.py   # Local version
│   ├── ingest_documents_railway.py # Railway version
│   └── migrate_bm25.py
├── docker-compose.yml
├── Dockerfile.railway   # Railway-specific Dockerfile
├── railway.toml         # Railway deployment config
├── RAILWAY_DEPLOYMENT.md # Detailed Railway guide
├── README-LOCAL.md      # Local setup without Docker
└── .env.example         # Environment template
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

## Local Setup (No Docker)

For local development without Docker, see [README-LOCAL.md](README-LOCAL.md).

## Environment Setup

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Required variables:
- `LLM_API_KEY` - Your Qwen/OpenAI API key
- `DATABASE_URL` or individual `DATABASE_*` variables

## License

MIT License - See LICENSE file for details.
