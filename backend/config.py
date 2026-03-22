"""
Configuration settings for the Clinic AI Assistant backend.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# Get individual config values with fallbacks for empty strings
def get_env_or_default(key, default):
    value = os.getenv(key, default)
    return value if value else default


# Database Configuration - prefer DATABASE_URL if available
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Railway provides DATABASE_URL, extract components or use as-is
    import psycopg2

    try:
        # Parse the URL to get connection info
        from urllib.parse import urlparse

        parsed = urlparse(DATABASE_URL)
        DATABASE_CONFIG = {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": parsed.path[1:] if parsed.path else "railway",
            "user": parsed.username or "postgres",
            "password": parsed.password or "",
        }
    except Exception:
        # Fallback to using URL directly in database.py
        DATABASE_CONFIG = {
            "host": get_env_or_default("DATABASE_HOST", "localhost"),
            "port": int(get_env_or_default("DATABASE_PORT", "5432")),
            "database": get_env_or_default("POSTGRES_DB", "clinic_db"),
            "user": get_env_or_default("POSTGRES_USER", "clinic_user"),
            "password": get_env_or_default("POSTGRES_PASSWORD", "clinic_password"),
        }
else:
    DATABASE_CONFIG = {
        "host": get_env_or_default("DATABASE_HOST", "localhost"),
        "port": int(get_env_or_default("DATABASE_PORT", "5432")),
        "database": get_env_or_default("POSTGRES_DB", "clinic_db"),
        "user": get_env_or_default("POSTGRES_USER", "clinic_user"),
        "password": get_env_or_default("POSTGRES_PASSWORD", "clinic_password"),
    }

# LLM API Configuration
LLM_API_KEY = get_env_or_default("LLM_API_KEY", "")
LLM_MODEL = get_env_or_default("LLM_MODEL", "kimi-k2.5")
LLM_API_URL = get_env_or_default(
    "LLM_API_URL", "https://coding-intl.dashscope.aliyuncs.com"
)

# Chunking Configuration
CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50

# Vector Search Configuration
VECTOR_SEARCH_TOP_K = 3

# SQL Safety
SQL_LIMIT = 100
