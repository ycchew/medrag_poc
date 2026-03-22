"""
Configuration settings for the Clinic AI Assistant backend.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DATABASE_CONFIG = {
    "host": os.getenv("DATABASE_HOST", "localhost"),
    "port": int(os.getenv("DATABASE_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "clinic_db"),
    "user": os.getenv("POSTGRES_USER", "clinic_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "clinic_password"),
}

# LLM API Configuration
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "kimi-k2.5")

# Chunking Configuration
CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50

# Vector Search Configuration
VECTOR_SEARCH_TOP_K = 3

# SQL Safety
SQL_LIMIT = 100
