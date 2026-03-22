# Guiding Principles for LLM-Powered Healthcare Applications

**Project:** Clinic AI Assistant (medrag_poc)  
**Context:** Proof-of-Concept RAG chatbot for clinic operations  
**Deployment Target:** Railway (Cloud Platform)  

---

## 1. Project Architecture Principles

### 1.1 Separation of Concerns

**Principle:** Strictly separate unstructured data (RAG) from structured data (SQL) pipelines.

```
✅ CORRECT:
├── RAG Pipeline → Vector Store → Clinical Guidelines
├── SQL Pipeline → PostgreSQL → Patient Records
└── Query Router → Classifies and routes appropriately

❌ WRONG:
├── Single pipeline handling both types
└── No clear data partitioning
```

**Rationale:** Prevents AI hallucination of patient data into general medical answers. Enables different retrieval strategies for different query types.

**Implementation:**
- Use explicit query classification (DOCUMENT_QUERY vs SQL_QUERY)
- Store clinical guidelines in document_chunks table (vector search)
- Store patient data in relational tables (SQL queries)
- Never embed patient-specific data

### 1.2 Synthetic Data for Privacy

**Principle:** Always use synthetic data for PoC demos handling sensitive information.

**Rules:**
- Generate fake patient names, IDs, dates of birth
- Use realistic but fictional clinical scenarios
- Document clearly that all data is computer-generated
- Never use real PHI (Protected Health Information) even in development

**Implementation in this project:**
- All CSV files contain synthetic data
- README explicitly states: "All patient data in this demo is synthetic"
- Generated via scripts/generate_synthetic_data.py

---

## 2. Development Principles

### 2.1 Environment Configuration

**Principle:** Never hardcode credentials or environment-specific values.

**Required Pattern:**
```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
DATABASE_PORT = int(os.getenv("DATABASE_PORT", "5432"))
LLM_API_KEY = os.getenv("LLM_API_KEY")

if not LLM_API_KEY:
    raise ValueError("LLM_API_KEY must be set")
```

**Anti-pattern:**
```python
# NEVER DO THIS
DATABASE_HOST = "localhost"  # Hardcoded
LLM_API_KEY = "sk-abc123"    # Exposed secret
```

**File Structure:**
```
.env              # Local development (gitignored)
.env.example      # Template with dummy values
.env.production   # Production variables (gitignored)
```

### 2.2 Local vs Docker vs Cloud

**Principle:** Support multiple deployment targets with minimal code duplication.

**Pattern:** Create target-specific scripts:

| Target | Script | Notes |
|--------|--------|-------|
| Docker | `import_csv_data.py` | Uses container paths |
| Local | `import_csv_data_local.py` | Uses localhost, loads .env |
| Railway | `import_csv_data_railway.py` | Uses DATABASE_URL |

**Key Insight:** Railway uses project root as Docker build context, not the Dockerfile location. Always test Docker builds locally before deploying.

### 2.3 Dependency Management

**Principle:** Keep production images under platform limits (Railway: 4GB).

**Strategy:**
```python
# requirements.txt - Full dependencies (local development)
sentence-transformers==3.2.0  # 2GB+ with PyTorch

# requirements.railway.txt - Minimal dependencies
# Use API embeddings instead of local models
```

**Lessons Learned:**
- Local sentence-transformers: +2GB to image
- DashScope API embeddings: ~10MB
- Trade-off: Latency vs Image size

---

## 3. Database Principles

### 3.1 Connection Strategy

**Principle:** Support both individual connection parameters and DSN strings.

**Implementation:**
```python
# config.py
def parse_database_url(url):
    """Parse DATABASE_URL into connection params."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return {
        "host": parsed.hostname,
        "port": parsed.port,
        "database": parsed.path[1:],
        "user": parsed.username,
        "password": parsed.password,
    }

# Usage
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASE_CONFIG = parse_database_url(DATABASE_URL)
else:
    DATABASE_CONFIG = {
        "host": os.getenv("DATABASE_HOST", "localhost"),
        # ...
    }
```

**Why:** Railway and Heroku provide DATABASE_URL. Local development uses individual vars.

### 3.2 Environment Variable Handling

**Critical Issue:** Empty strings are truthy in Python.

```python
# DANGER - Empty string passes check
host = os.getenv("DATABASE_HOST", "localhost")
# If DATABASE_HOST="", host becomes "" not "localhost"

# SAFE - Check for empty strings
def get_env_or_default(key, default):
    value = os.getenv(key)
    return value if value else default

host = get_env_or_default("DATABASE_HOST", "localhost")
```

### 3.3 Schema Management

**Principle:** Separate schema creation from data import.

```sql
-- data/sql/init_schema.sql
-- Run once to create tables and extensions

-- scripts/import_csv_data.py
-- Run after schema exists to populate data
```

**Deployment Order:**
1. Create PostgreSQL instance
2. Run init_schema.sql
3. Import CSV data
4. Ingest documents (generate embeddings)

---

## 4. API Development Principles

### 4.1 FastAPI Route Ordering

**Critical Issue:** StaticFiles mount order matters.

```python
# WRONG - StaticFiles intercepts all routes
app.mount("/", StaticFiles(...), name="frontend")  # Blocks /api/*

app.get("/api/health")  # Never reached
app.get("/api/chat")    # Never reached
```

```python
# CORRECT - Define API routes first
app.get("/api/health")
app.get("/api/chat")
app.get("/api/dashboard")
# ... all API routes ...

# Mount static files LAST
app.mount("/", StaticFiles(...), name="frontend")
```

### 4.2 CORS Configuration

**Development:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Production:**
```python
allow_origins=[
    "https://your-domain.com",
    "https://app.your-domain.com"
]
```

### 4.3 Health Checks

**Always implement a health endpoint:**
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "database": check_db_connection(),
            "llm": check_llm_connection()
        }
    }
```

**Why:** Deployment platforms (Railway, Render, etc.) use health checks to determine if your app is ready.

---

## 5. Deployment Principles

### 5.1 Docker Best Practices

**Image Size Optimization:**
```dockerfile
# Use slim base images
FROM python:3.11-slim

# Multi-stage builds for compiled dependencies
FROM python:3.11-slim as builder
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
```

**Port Configuration:**
```dockerfile
# Hardcode port in container
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Platform Mapping:**
- Railway proxies external URL → internal port automatically
- Don't use `$PORT` env var in Dockerfile (expansion issues)
- Match railway.toml port with Dockerfile port

### 5.2 Platform-Specific Configurations

**Railway.toml Pattern:**
```toml
[build]
dockerfilePath = "Dockerfile.railway"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port 8000"
healthcheckPath = "/health"
healthcheckTimeout = 300
```

**Why Separate Dockerfiles:**
- `Dockerfile` - Local development with all dependencies
- `Dockerfile.railway` - Production optimized, minimal size
- Different COPY paths (Railway context is project root)

### 5.3 Environment Variable Strategy

**Railway Variables:**
```bash
# Database (auto-generated by Railway PostgreSQL)
DATABASE_URL=postgresql://user:pass@host:port/db

# LLM Configuration
LLM_API_KEY=sk-xxx
LLM_API_URL=https://coding-intl.dashscope.aliyuncs.com
LLM_MODEL=qwen3.5-plus
```

**Local Variables:**
```bash
# Individual connection params
DATABASE_HOST=localhost
DATABASE_PORT=5432
POSTGRES_DB=clinic_db
POSTGRES_USER=clinic_user
POSTGRES_PASSWORD=clinic_password
```

**Code Support:**
```python
# Support both patterns
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Use DSN
    config = parse_database_url(database_url)
else:
    # Use individual vars
    config = {
        "host": os.getenv("DATABASE_HOST", "localhost"),
        # ...
    }
```

---

## 6. Testing & Debugging Principles

### 6.1 Local Testing Before Deployment

**Checklist:**
1. ✅ Docker build succeeds locally
2. ✅ Container starts without errors
3. ✅ Health endpoint responds
4. ✅ Database connections work
5. ✅ LLM API calls succeed
6. ✅ Frontend loads and connects to API

**Local Docker Test:**
```bash
# Build
DOCKER_BUILDKIT=1 docker build -f Dockerfile.railway -t medrag:test .

# Run with env vars
docker run -p 8000:8000 --env-file .env medrag:test

# Test
curl http://localhost:8000/health
```

### 6.2 Debugging Deployment Issues

**Logs Are Essential:**
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log key events
logger.info(f"Connecting to database at {host}:{port}")
logger.error(f"Database connection failed: {e}")
```

**Common Issues:**

| Symptom | Cause | Solution |
|---------|-------|----------|
| 404 on /health | StaticFiles mounted first | Move mount to end of main.py |
| Database connection refused | Wrong host/port | Use DATABASE_URL or check env vars |
| Image too large | ML libraries | Use API embeddings, remove heavy deps |
| Port not accessible | $PORT not set | Hardcode port 8000 |
| Missing config | .gitignore excluded | Force add or fix .gitignore |

### 6.3 Monitoring

**Add to FastAPI:**
```python
from fastapi import Request
import time

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

---

## 7. Security Principles

### 7.1 Secrets Management

**Never commit secrets:**
```bash
# .gitignore
.env
.env.local
.env.production
*.pem
*.key
```

**Use platform secret management:**
- Railway: Variables tab (encrypted at rest)
- Render: Environment variables (encrypted)
- Local: .env file (never committed)

### 7.2 Database Security

**Principles:**
1. Use read-only database users for app connections
2. Enable SSL for database connections in production
3. Use connection pooling (pgbouncer for high traffic)
4. Implement query timeouts (prevent long-running queries)

**Implementation:**
```python
# database.py
DBPool = ThreadedConnectionPool(
    minconn=2,
    maxconn=10,
    host=host,
    # ...
    sslmode="require" if is_production else "prefer",
    connect_timeout=10
)
```

### 7.3 API Security

**Input Validation:**
```python
from pydantic import BaseModel, Field, validator

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    session_id: str = Field(default="default", max_length=100)
    
    @validator('question')
    def validate_question(cls, v):
        if not v.strip():
            raise ValueError('Question cannot be empty')
        return v.strip()
```

**Rate Limiting:**
```python
from slowapi import Limiter

limiter = Limiter(key_func=lambda: "global")
app.state.limiter = limiter

@app.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, query: QueryRequest):
    # ...
```

---

## 8. Cost Optimization Principles

### 8.1 LLM API Usage

**Minimize token usage:**
```python
# Cache embeddings for duplicate queries
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_embedding(text: str):
    return llm_client.embed(text)

# Use cheaper models for routing
classification_model = "qwen-turbo"  # Cheaper
response_model = "qwen3.5-plus"       # Better quality
```

### 8.2 Database Optimization

**Query Limits:**
```python
# Always limit results
@app.get("/api/patients")
async def get_patients(limit: int = Query(default=100, le=1000)):
    return db.query(Patient).limit(limit).all()
```

**Connection Pooling:**
- Min: 2 connections
- Max: 10 connections (prevents overwhelming database)
- Recycle connections every hour (prevents stale connections)

### 8.3 Free Tier Strategy

**Railway Free Tier ($5/month credit):**
- ~500 hours of runtime
- Services hibernate after inactivity
- Database hibernates after 1 hour
- **Strategy:** Acceptable for demos, not production

**Cost-Saving Tips:**
1. Use API embeddings instead of local models
2. Implement aggressive caching
3. Use cheaper LLM models for simple tasks
4. Add request rate limiting
5. Monitor usage in Railway dashboard

---

## 9. Documentation Principles

### 9.1 README Structure

**Required Sections:**
1. **Overview** - What this project does
2. **Quick Start** - Get running in 5 minutes
3. **Architecture** - High-level system design
4. **Data Privacy** - How sensitive data is handled
5. **Deployment** - Step-by-step guide
6. **Troubleshooting** - Common issues and solutions

**Example:** See README.md and README-LOCAL.md

### 9.2 Deployment Documentation

**Required for each platform:**
- Environment variables needed
- Service dependencies (databases, etc.)
- Build configuration
- Deployment steps
- Post-deployment setup (database init)

**File:** RAILWAY_DEPLOYMENT.md

### 9.3 Code Documentation

**Principle:** Code should be self-explanatory. Comments explain WHY, not WHAT.

```python
# Bad - Explains what code does
# Loop through patients and add them to list
for patient in patients:
    patient_list.append(patient)

# Good - Explains why
# Build patient list for batch processing
# to minimize database round-trips
patient_list = [p for p in patients]
```

---

## 10. Lessons Learned Summary

### Critical Issues Encountered

1. **Image Size (8.2GB)**
   - sentence-transformers + PyTorch too large
   - Solution: Switch to API embeddings
   - Time saved: Eliminated deployment failures

2. **Dockerfile Paths**
   - Railway context is project root
   - Solution: Dockerfile at root, adjust COPY paths
   - Time saved: Hours of debugging build failures

3. **PORT Variable**
   - $PORT doesn't expand in CMD
   - Solution: Hardcode port 8000
   - Time saved: Resolved startup failures

4. **Static Files Mount**
   - Mounted at / blocked API routes
   - Solution: Mount after all API routes
   - Time saved: Fixed 404 errors on all endpoints

5. **Empty String Env Vars**
   - os.getenv returns "" not None
   - Solution: get_env_or_default helper
   - Time saved: Database connection issues resolved

6. **Missing Files**
   - .gitignore excluded config.py
   - Solution: Force add, fix .gitignore
   - Time saved: Deployment worked first time after fix

### Key Takeaways

| Principle | Impact |
|-----------|--------|
| Test Docker builds locally | Prevents deployment surprises |
| Support multiple env patterns | DATABASE_URL + individual vars |
| Keep images small | <4GB for Railway |
| Order matters in FastAPI | API routes before StaticFiles |
| Document everything | Future you will thank you |
| Use synthetic data | Privacy-safe demos |
| Health checks | Required for platform integration |

---

## Appendix: File Organization

```
medrag_poc/
├── backend/                    # FastAPI application
│   ├── main.py                # Entry point
│   ├── config.py              # Environment configuration
│   ├── database.py            # Database connection
│   ├── services/              # Business logic
│   │   ├── query_router.py
│   │   ├── rag_service.py
│   │   ├── text_to_sql.py
│   │   └── llm_client.py
│   ├── prompts.py             # LLM prompts
│   ├── requirements.txt       # Full dependencies
│   └── requirements.railway.txt  # Minimal dependencies
├── frontend/                  # Static HTML
│   ├── index.html            # Docker version (relative API)
│   └── index_local.html      # Local development version
├── data/
│   ├── docs/                 # Medical guidelines (RAG)
│   └── sql/                  # Synthetic data (CSV)
├── scripts/                  # Setup scripts
│   ├── import_csv_data.py           # Docker
│   ├── import_csv_data_local.py     # Local
│   ├── import_csv_data_railway.py   # Railway
│   ├── ingest_documents.py          # Docker
│   ├── ingest_documents_local.py    # Local
│   ├── ingest_documents_railway.py  # Railway
│   └── generate_synthetic_data.py
├── Dockerfile                # Local development
├── Dockerfile.railway        # Production optimized
├── railway.toml             # Railway configuration
├── docker-compose.yml       # Local Docker setup
├── .env.example            # Environment template
├── .gitignore             # Git exclusions
├── README.md              # Main documentation
├── README-LOCAL.md        # Local setup guide
└── RAILWAY_DEPLOYMENT.md  # Railway deployment guide
```

---

**Last Updated:** March 2024  
**Project:** Clinic AI Assistant PoC  
**Deployment:** Railway (Cloud)  
**License:** MIT (for demo purposes)
