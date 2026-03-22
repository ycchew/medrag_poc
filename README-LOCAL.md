# Clinic AI Assistant - Local Setup Guide

A Proof of Concept (PoC) RAG chatbot for a clinic group database. **Based on real-world clinical requirements**, this demo uses **synthetic patient data** to demonstrate AI-powered clinical assistants.

This guide helps you set up the application **without Docker**, using your existing local PostgreSQL database.

> **Important Note**: All patient data in this demo is **synthetic** (computer-generated). Patient names, IDs, visit records, and clinical notes are fictional and created solely for demonstration purposes. No real patient information is used.

## Prerequisites

- **PostgreSQL 14+** with [pgvector extension](https://github.com/pgvector/pgvector) installed
- **Python 3.11+**
- **Node.js** (optional - for serving frontend, or use any static file server)
- **LLM API key** (Qwen3.5 Plus or OpenAI)

---

## Data Privacy & Synthetic Data

This application demonstrates a **real-world clinical use case** using entirely **synthetic data**:

- **Patient Records**: All names, IDs, dates of birth, and demographics are computer-generated
- **Visit Data**: All visit dates, diagnoses, prescriptions, and clinical notes are fictional
- **Clinic Data**: Clinic names and locations are examples only

This approach allows demonstration of the system's capabilities while ensuring **zero privacy concerns** - no real patient information is ever used or exposed.

---

## Step 1: Install PostgreSQL with pgvector

### macOS (using Homebrew)
```bash
brew install postgresql
brew install pgvector
```

### Ubuntu/Debian
```bash
# Install PostgreSQL
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Install pgvector
sudo apt-get install postgresql-server-dev-XX  # Replace XX with your PG version
sudo apt-get install pgvector
```

### Windows
1. Download PostgreSQL from https://www.postgresql.org/download/windows/
2. Download pgvector from https://github.com/pgvector/pgvector/releases
3. Extract pgvector to PostgreSQL's `share/extension` folder

### Enable pgvector Extension
Connect to your PostgreSQL database and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Step 2: Configure Environment Variables

Create a `.env` file in the project root:

```env
# Database Configuration (adjust to your local PostgreSQL)
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=clinic_db
DATABASE_HOST=localhost
DATABASE_PORT=5432

# LLM API Configuration
LLM_MODEL=qwen3.5-plus
LLM_API_URL=https://coding-intl.dashscope.aliyuncs.com
LLM_API_KEY=your_api_key_here
```

**Note**: Replace `your_db_user`, `your_db_password`, and `your_api_key_here` with your actual values.

---

## Step 3: Install Python Dependencies

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 4: Initialize the Database

### 4.1 Create Database and Schema

Connect to PostgreSQL and create the database:
```bash
# Connect to PostgreSQL (adjust username as needed)
psql -U your_db_user -d postgres
```

Create the database:
```sql
CREATE DATABASE clinic_db;
\q
```

### 4.2 Run Schema Initialization

```bash
# Connect to the new database and run the schema script
psql -U your_db_user -d clinic_db -f data/sql/init_schema.sql
```

This creates:
- **Relational tables**: clinics, patients, visits, diagnoses, prescriptions, clinical_notes
- **Vector table**: document_chunks (created automatically by backend)

---

## Step 5: Import Synthetic Data

### 5.1 Import CSV Data

```bash
# For docker version
python scripts/import_csv_data.py

# For local version, ensure python-dotenv is installed
pip install python-dotenv psycopg2-binary
python scripts/import_csv_data_local.py
# The script automatically loads credentials from .env and connects to localhost by default.
```

This imports data from:
- `data/sql/clinics.csv`
- `data/sql/patients.csv`
- `data/sql/visits.csv`
- `data/sql/diagnoses.csv`
- `data/sql/prescriptions.csv`
- `data/sql/clinical_notes.csv`

### 5.2 Adjust Visit Patterns

```bash
# For Docker
python scripts/adjust_visits_by_day.py
# For local
python scripts/adjust_visits_by_day_local.py
```

---

## Step 6: Ingest Documents for RAG

```bash
# Pre-requisite
# Make sure the clinic_db has created vector extension
# For Docker
python scripts/ingest_documents.py
# For local
python scripts/ingest_documents_local.py
```

This processes all `.md` files in `data/docs/` and creates embeddings in the `document_chunks` table.

**Required**: Make sure `LLM_API_KEY` is set in your `.env` file before running this.

### 6.1 Add BM25 Full-Text Search (Optional but Recommended)

```bash
# For Docker
python scripts/migrate_bm25.py
# For local
python scripts/migrate_bm25_local.py
```

This enables hybrid search (vector + BM25) for better document retrieval.

---

## Step 7: Start the Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Base**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## Step 8: Serve the Frontend

The frontend is a static HTML file. You can serve it using any method:

### Option A: Python Simple HTTP Server
```bash
cd frontend
python -m http.server 3000
```
Access at: http://localhost:3000

### Option B: Using VS Code Live Server Extension
Install the "Live Server" extension and right-click on `index.html` → "Open with Live Server"

### Option C: Node.js (npx serve)
```bash
cd frontend
npx serve -p 3000
```

### Option D: Nginx (Production)
Configure nginx to serve the `frontend/` directory on port 3000.

---

## All-in-One Setup Script

For convenience, you can run all setup steps with:

```bash
# Install dependencies
cd backend && pip install -r requirements.txt && cd ..

# Set environment variables
export $(cat .env | xargs)  # Linux/Mac
# OR on Windows: for /f "tokens=*" %i in (.env) do set %i

# Initialize database
psql -U $POSTGRES_USER -d $POSTGRES_DB -f data/sql/init_schema.sql

# Import data
python scripts/import_csv_data.py
python scripts/adjust_visits_by_day.py

# Ingest documents (requires LLM_API_KEY)
python scripts/ingest_documents.py
python scripts/migrate_bm25.py

# Start backend
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 &

# Start frontend (in another terminal)
cd frontend && python -m http.server 3000
```

---

## Project Structure

```
.
├── backend/              # FastAPI application
│   ├── main.py          # API entry point
│   ├── database.py      # DB connection + schema init
│   ├── config.py        # Configuration settings
│   ├── requirements.txt # Python dependencies
│   └── services/
│       ├── llm_client.py       # LLM API integration
│       ├── rag_service.py      # RAG (chunking, embeddings, search)
│       ├── query_router.py     # Query classification
│       ├── text_to_sql.py      # SQL generation & execution
│       └── dashboard_service.py # Statistics & charts
├── frontend/            # Static HTML + Tailwind CSS
│   └── index.html      # Single-page application
├── data/
│   ├── docs/           # Medical guidelines (RAG source)
│   │   ├── asthma.md
│   │   ├── diabetes.md
│   │   ├── dengue.md
│   │   ├── gerd.md
│   │   ├── hypertension.md
│   │   └── triage.md
│   └── sql/            # Synthetic clinic data (CSV files) - computer-generated
│       ├── clinics.csv
│       ├── patients.csv
│       ├── visits.csv
│       ├── diagnoses.csv
│       ├── prescriptions.csv
│       ├── clinical_notes.csv
│       └── init_schema.sql
├── scripts/            # Setup and ingestion scripts
│   ├── import_csv_data.py      # Import CSV data
│   ├── ingest_documents.py     # Ingest documents for RAG
│   ├── adjust_visits_by_day.py # Adjust visit patterns
│   └── migrate_bm25.py         # Add BM25 search
└── .env                # Environment configuration
```

---

## Troubleshooting

### Issue: "pgvector extension not found"
**Solution**: Install pgvector for your PostgreSQL version:
```bash
# macOS
brew install pgvector

# Ubuntu/Debian
sudo apt-get install postgresql-server-dev-XX pgvector
```

### Issue: "ImportError: No module named 'psycopg2'"
**Solution**: Install psycopg2-binary:
```bash
pip install psycopg2-binary
```

### Issue: "Connection refused" to PostgreSQL
**Solution**: 
1. Ensure PostgreSQL is running: `sudo service postgresql start` (Linux) or `brew services start postgresql` (macOS)
2. Check your `.env` file has correct DATABASE_HOST (use `localhost` or `127.0.0.1`)
3. Verify PostgreSQL is listening on the correct port: `sudo netstat -plntu | grep 5432`

### Issue: "LLM_API_KEY not set"
**Solution**: Ensure your `.env` file is in the project root and contains `LLM_API_KEY=your_key_here`

### Issue: Frontend can't connect to backend
**Solution**: 
1. Ensure backend is running on port 8000
2. Check CORS is enabled in `backend/main.py` (line 43-49)
3. If using a different frontend port, update the `API_URL` in `frontend/index.html` (line 164) to point to `http://localhost:8000`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| POST | /chat | Auto-routed query (RAG or SQL) |
| POST | /rag | Document query only |
| POST | /sql-query | Patient data query only |
| POST | /classify | Classify query type |
| GET | /dashboard/all | All dashboard data |
| GET | /history/{session_id} | Chat history |

---

## Demo Scenarios

Once everything is running, try these questions in the chat:

### Clinical Knowledge (RAG)
- "What is the treatment for hypertension?"
- "What are the first-line medications for asthma?"
- "How do I triage a patient with chest pain?"

### Clinic Statistics (SQL)
- "How many diabetic patients visited last month?"
- "Which clinic has the most dengue cases?"
- "What is the most prescribed medication?"

---

## Stopping the Application

To stop the backend:
- Press `Ctrl+C` in the terminal running uvicorn

To stop the frontend:
- Press `Ctrl+C` in the terminal running the HTTP server

---

## Data Partitioning

The system uses strict data partitioning:

1. **Relational Schema (SQL Target)**: Structured data + patient-specific unstructured text
   - Patient demographics, visit records, diagnoses, prescriptions
   - Clinical notes (stored as standard text, NOT embedded)

2. **Vector Schema (RAG Target)**: General medical knowledge ONLY
   - Standard Operating Procedures
   - Medical Treatment Guidelines
   - Drug Formularies

This prevents the AI from hallucinating patient data into general medical answers.
