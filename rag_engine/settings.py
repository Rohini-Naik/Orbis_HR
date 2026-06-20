"""Central settings loader for environment-backed configuration.

Loads `.env` (if present) and exposes commonly used settings as variables
and helper functions. Other modules should import values from here instead
of reading `os.environ` directly.
"""
from __future__ import annotations

import os
from typing import Dict, Any

from dotenv import load_dotenv

from rag_engine import config as _config


# Load .env from project root if present
ROOT = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(ROOT, ".env")
load_dotenv(ENV_PATH)


# Keys
HUGGINGFACE_API_KEY: str | None = os.getenv("HUGGINGFACE_API_KEY")

# MySQL
MYSQL_HOST: str | None = os.getenv("MYSQL_HOST")
MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER: str | None = os.getenv("MYSQL_USER")
MYSQL_PASSWORD: str | None = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE: str | None = os.getenv("MYSQL_DATABASE")

# API Key for service
API_KEY: str | None = os.getenv("API_KEY")

# Embedding model override: fallback to config.EMBEDDING_MODEL_NAME
EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME") or _config.EMBEDDING_MODEL_NAME
 
# Hugging Face LLM model choices (can be overridden via .env)
HF_ANSWER_MODEL: str | None = os.getenv("HF_ANSWER_MODEL") or "meta-llama/Llama-3.1-8B-Instruct"
HF_SQL_MODEL: str | None = os.getenv("HF_SQL_MODEL") or "defog/sqlcoder-7b-2"


def get_mysql_config() -> Dict[str, Any]:
    """Return a dict suitable for `mysql.connector.connect()`.

    Values come from env vars (or None). Caller should validate non-None
    credentials before attempting a connection.
    """
    return {
        "host": MYSQL_HOST or "localhost",
        "port": MYSQL_PORT,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "database": MYSQL_DATABASE,
    }


__all__ = [
    "HUGGINGFACE_API_KEY",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
    "API_KEY",
    "EMBEDDING_MODEL_NAME",
    "HF_ANSWER_MODEL",
    "HF_SQL_MODEL",
    "get_mysql_config",
]
