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

# MySQL — read-only HR data (employees), used by NL->SQL
MYSQL_HOST: str | None = os.getenv("MYSQL_HOST")
MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER: str | None = os.getenv("MYSQL_USER")
MYSQL_PASSWORD: str | None = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE: str | None = os.getenv("MYSQL_DATABASE")

# MySQL — read-write application state (users, sessions, conversations, audit),
# isolated from the HR data with its own user and database.
MYSQL_APP_USER: str | None = os.getenv("MYSQL_APP_USER") or "orbis_app"
MYSQL_APP_PASSWORD: str | None = os.getenv("MYSQL_APP_PASSWORD")
MYSQL_APP_DATABASE: str | None = os.getenv("MYSQL_APP_DATABASE") or "orbis_app"

# MySQL — read-write HR data, used ONLY by admin employee-management endpoints.
# NL->SQL keeps using the read-only MYSQL_USER above.
MYSQL_HR_ADMIN_USER: str | None = os.getenv("MYSQL_HR_ADMIN_USER") or "orbis_hr_admin"
MYSQL_HR_ADMIN_PASSWORD: str | None = os.getenv("MYSQL_HR_ADMIN_PASSWORD")

# Embedding model override: fallback to config.EMBEDDING_MODEL_NAME
EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME") or _config.EMBEDDING_MODEL_NAME
 
# Hugging Face LLM model choices (can be overridden via .env)
HF_ANSWER_MODEL: str | None = os.getenv("HF_ANSWER_MODEL") or "meta-llama/Llama-3.1-8B-Instruct"
HF_SQL_MODEL: str | None = os.getenv("HF_SQL_MODEL") or "meta-llama/Llama-3.1-8B-Instruct"


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


def get_app_mysql_config() -> Dict[str, Any]:
    """Connection config for the read-write application-state database."""
    return {
        "host": MYSQL_HOST or "localhost",
        "port": MYSQL_PORT,
        "user": MYSQL_APP_USER,
        "password": MYSQL_APP_PASSWORD,
        "database": MYSQL_APP_DATABASE,
    }


def get_hr_admin_mysql_config() -> Dict[str, Any]:
    """Read-write connection to the HR database for admin employee management."""
    return {
        "host": MYSQL_HOST or "localhost",
        "port": MYSQL_PORT,
        "user": MYSQL_HR_ADMIN_USER,
        "password": MYSQL_HR_ADMIN_PASSWORD,
        "database": MYSQL_DATABASE,
    }


__all__ = [
    "HUGGINGFACE_API_KEY",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
    "MYSQL_APP_USER",
    "MYSQL_APP_PASSWORD",
    "MYSQL_APP_DATABASE",
    "MYSQL_HR_ADMIN_USER",
    "MYSQL_HR_ADMIN_PASSWORD",
    "EMBEDDING_MODEL_NAME",
    "HF_ANSWER_MODEL",
    "HF_SQL_MODEL",
    "get_mysql_config",
    "get_app_mysql_config",
    "get_hr_admin_mysql_config",
]
