# Clinic AI Assistant - Railway Deployment Guide

This guide walks you through deploying the Clinic AI Assistant to Railway for free demo hosting.

## Prerequisites

1. [Railway account](https://railway.app/) (free tier available)
2. [GitHub account](https://github.com/) with your code pushed
3. Your repository: `https://github.com/ycchew/medrag_poc`

---

## Step 1: Connect Railway to GitHub

1. Log in to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `medrag_poc` repository
4. Railway will detect the `railway.toml` configuration

---

## Step 2: Add PostgreSQL Database with pgvector

1. In your Railway project, click **"New"** → **"Database"** → **"Add PostgreSQL"**
2. Once created, click on the PostgreSQL service
3. Go to **"Settings"** tab
4. Under **"Extensions"**, ensure `vector` extension is enabled (Railway enables this by default)

---

## Step 3: Configure Environment Variables

1. Click on your **app service** (the FastAPI backend)
2. Go to **"Variables"** tab
3. Add the following variables:

### Required Variables

| Variable | Value | Source |
|----------|-------|--------|
| `DATABASE_HOST` | `${{Postgres.PGHOST}}` | Reference from Postgres service |
| `DATABASE_PORT` | `${{Postgres.PGPORT}}` | Reference from Postgres service |
| `POSTGRES_DB` | `${{Postgres.PGDATABASE}}` | Reference from Postgres service |
| `POSTGRES_USER` | `${{Postgres.PGUSER}}` | Reference from Postgres service |
| `POSTGRES_PASSWORD` | `${{Postgres.PGPASSWORD}}` | Reference from Postgres service |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Full connection string |
| `LLM_API_KEY` | `your_actual_api_key` | Your DashScope/Qwen API key |
| `LLM_API_URL` | `https://coding-intl.dashscope.aliyuncs.com` | API endpoint |
| `LLM_MODEL` | `qwen3.5-plus` | Model name |
| `PORT` | `8000` | Railway sets this automatically |

### How to Add References

Click **"New Variable"** → **"Add Reference"** → Select your PostgreSQL service → Choose the variable.

For `LLM_API_KEY`, paste your actual API key directly.

---

## Step 4: Configure Public Domain

1. Click on your **app service**
2. Go to **"Settings"** tab
3. Under **"Public Networking"**, click **"Generate Domain"**
4. Railway will provide a URL like: `https://medrag-poc-production.up.railway.app`

---

## Step 5: Deploy

Railway deploys automatically when you push to GitHub. For manual deployment:

1. In Railway dashboard, click on your service
2. Go to **"Deployments"** tab
3. Click **"Deploy"** if needed

Wait for deployment to complete (takes 2-5 minutes for initial build).

---

## Step 6: Verify Deployment

### Check Health Endpoint

Visit: `https://your-app-url.railway.app/health`

Expected response:
```json
{
  "status": "healthy",
  "services": {
    "database": true,
    "llm": true
  }
}
```

### Test API

Visit: `https://your-app-url.railway.app/docs`

You should see the FastAPI Swagger UI.

---

## Step 7: Initialize Database (One-time Setup)

### Option A: Railway CLI (Recommended)

1. Install [Railway CLI](https://docs.railway.app/guides/cli):
   ```bash
   npm install -g @railway/cli
   ```

2. Login and link:
   ```bash
   railway login
   railway link
   ```

3. Run database initialization:
   ```bash
   railway run psql -f data/sql/init_schema.sql
   ```

4. Import data:
   ```bash
   railway run python scripts/import_csv_data_railway.py
   ```

### Option B: Manual via Railway Console

1. In Railway dashboard, click on your PostgreSQL service
2. Go to **"Connect"** tab
3. Use the connection string with a local PostgreSQL client:
   ```bash
   psql "your_railway_connection_string" -f data/sql/init_schema.sql
   ```

---

## Step 8: Ingest Documents (RAG Setup)

After database is initialized, ingest the medical guidelines:

```bash
# Using Railway CLI
railway run python scripts/ingest_documents_railway.py
```

Or run locally with Railway connection:
```bash
export DATABASE_URL="your_railway_database_url"
python scripts/ingest_documents_local.py
```

---

## Frontend Deployment (Optional)

The frontend is a static HTML file. You have two options:

### Option A: Serve via Backend (Easiest)

The backend already serves static files. Update `main.py` to serve the frontend:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
```

Then access your app directly at the Railway URL.

### Option B: Separate Vercel Deployment

Deploy frontend separately to Vercel:

1. Push frontend code to a separate repo or folder
2. Connect Vercel to that folder
3. Update `index_local.html` to point to your Railway backend URL

---

## Monitoring & Logs

### View Logs

1. In Railway dashboard, click on your service
2. Go to **"Logs"** tab
3. View real-time logs and deployment history

### Set Up Alerts

1. Go to **"Settings"** → **"Notifications"**
2. Configure webhook or email alerts for deployment failures

---

## Troubleshooting

### Database Connection Errors

**Problem:** `could not connect to server: Connection refused`

**Solution:**
- Verify all `DATABASE_*` variables are set correctly
- Use Railway's variable references, not hardcoded values
- Check that PostgreSQL service is running (green dot)

### pgvector Extension Not Found

**Problem:** `ERROR: extension "vector" does not exist`

**Solution:**
- Railway enables pgvector by default on new PostgreSQL instances
- If missing, run: `CREATE EXTENSION vector;` in PostgreSQL console

### Build Failures

**Problem:** Docker build fails

**Solution:**
- Check `railway.toml` points to correct Dockerfile path
- Verify `requirements.txt` has all dependencies
- Check build logs in Railway dashboard

### LLM API Errors

**Problem:** LLM health check fails

**Solution:**
- Verify `LLM_API_KEY` is set correctly
- Check API key has sufficient credits
- Verify `LLM_API_URL` is correct for your provider

---

## Free Tier Limits

Railway's free tier includes:
- **$5/month credit** (approximately 500 hours of runtime)
- **1GB RAM** per service
- **1GB Disk** for PostgreSQL
- **Shared CPU**

**Cost-saving tips:**
- Railway pauses services after inactivity (wakes on next request)
- PostgreSQL hibernates after 1 hour of inactivity
- First 500 hours/month are essentially free

---

## Custom Domain (Optional)

1. Go to your service **Settings**
2. Under **"Public Networking"**, click **"Custom Domain"**
3. Add your domain (e.g., `clinic-demo.yourdomain.com`)
4. Follow DNS configuration instructions

---

## Next Steps

After successful deployment:

1. ✅ Test the `/health` endpoint
2. ✅ Initialize database schema
3. ✅ Import synthetic data
4. ✅ Ingest medical documents
5. ✅ Share your demo URL!

Your Clinic AI Assistant is now live on Railway!

---

## Quick Reference Commands

```bash
# View logs
railway logs

# Run database migration
railway run python scripts/import_csv_data_railway.py

# Open PostgreSQL console
railway connect postgres

# Redeploy
railway up
```

## Support

- [Railway Documentation](https://docs.railway.app/)
- [Railway Discord](https://discord.gg/railway)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
