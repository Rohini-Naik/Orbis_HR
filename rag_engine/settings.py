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
 
# --- Generative model provider ----------------------------------------
# Both providers speak the same chat-completions API; see rag_engine/llm.py.
# Defaults to Groq when a key is present so a depleted Hugging Face quota does
# not require a code change.
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
LLM_PROVIDER: str = (
    os.getenv("LLM_PROVIDER") or ("groq" if GROQ_API_KEY else "huggingface")
).lower()

# Hugging Face model ids
HF_ANSWER_MODEL: str = os.getenv("HF_ANSWER_MODEL") or "meta-llama/Llama-3.1-8B-Instruct"
HF_SQL_MODEL: str = os.getenv("HF_SQL_MODEL") or "meta-llama/Llama-3.1-8B-Instruct"

# Reasoning budget for models that support it ('low' | 'medium' | 'high').
# Low keeps latency and token use down; the SQL task needs no deliberation.
GROQ_REASONING_EFFORT: str = os.getenv("GROQ_REASONING_EFFORT", "low").strip()

# Groq model ids. Routing is a three-way classification, so it uses a small
# fast model rather than the reasoning model used for answers and SQL — it is
# quicker, cheaper, and spends no tokens deliberating.
GROQ_ANSWER_MODEL: str = os.getenv("GROQ_ANSWER_MODEL") or "openai/gpt-oss-120b"
GROQ_SQL_MODEL: str = os.getenv("GROQ_SQL_MODEL") or "openai/gpt-oss-120b"
GROQ_ROUTER_MODEL: str = os.getenv("GROQ_ROUTER_MODEL") or "llama-3.1-8b-instant"

# Resolved ids the application uses. Call sites reference these rather than a
# provider-specific name, so switching provider changes nothing downstream.
ANSWER_MODEL: str = GROQ_ANSWER_MODEL if LLM_PROVIDER == "groq" else HF_ANSWER_MODEL
SQL_MODEL: str = GROQ_SQL_MODEL if LLM_PROVIDER == "groq" else HF_SQL_MODEL
ROUTER_MODEL: str = GROQ_ROUTER_MODEL if LLM_PROVIDER == "groq" else HF_ANSWER_MODEL

# --- Employer identity -------------------------------------------------
# The organisation this deployment serves. Company email addresses are minted
# from COMPANY_EMAIL_DOMAIN and are the login identity for every account.
COMPANY_NAME: str = os.getenv("COMPANY_NAME") or "Orbis"
COMPANY_EMAIL_DOMAIN: str = os.getenv("COMPANY_EMAIL_DOMAIN") or "orbis.com"

# --- Onboarding email --------------------------------------------------
# 'console' prints invites to the server log — no configuration, and nothing
# can reach a real inbox by accident. Switch to 'smtp' to send for real.
EMAIL_BACKEND: str = (os.getenv("EMAIL_BACKEND") or "console").lower()
EMAIL_FROM: str = os.getenv("EMAIL_FROM") or f"no-reply@{COMPANY_EMAIL_DOMAIN}"
SMTP_HOST: str | None = os.getenv("SMTP_HOST")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
SMTP_USER: str | None = os.getenv("SMTP_USER")
SMTP_PASSWORD: str | None = os.getenv("SMTP_PASSWORD")
SMTP_USE_TLS: bool = (os.getenv("SMTP_USE_TLS") or "true").lower() == "true"

# Base URL of the frontend, used to build the set-password link in invites.
APP_BASE_URL: str = (os.getenv("APP_BASE_URL") or "http://localhost:5173").rstrip("/")

# How long an onboarding invite stays valid.
INVITE_TTL_DAYS: int = int(os.getenv("INVITE_TTL_DAYS", 7))


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
    "GROQ_API_KEY",
    "GROQ_REASONING_EFFORT",
    "GROQ_ANSWER_MODEL",
    "GROQ_ROUTER_MODEL",
    "GROQ_SQL_MODEL",
    "LLM_PROVIDER",
    "ANSWER_MODEL",
    "SQL_MODEL",
    "ROUTER_MODEL",
    "COMPANY_NAME",
    "COMPANY_EMAIL_DOMAIN",
    "EMAIL_BACKEND",
    "EMAIL_FROM",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_USE_TLS",
    "APP_BASE_URL",
    "INVITE_TTL_DAYS",
    "get_mysql_config",
    "get_app_mysql_config",
    "get_hr_admin_mysql_config",
]
