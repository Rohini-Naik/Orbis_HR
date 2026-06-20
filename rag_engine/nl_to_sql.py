import os
import re
from typing import List, Any

# Use settings for config
from rag_engine import settings

# Hugging Face Inference client availability
HF_AVAILABLE = False
try:
    from huggingface_hub import InferenceClient

    HF_AVAILABLE = True
except Exception:
    HF_AVAILABLE = False

# MySQL client (optional)
MYSQL_AVAILABLE = False
try:
    import mysql.connector

    MYSQL_AVAILABLE = True
except Exception:
    MYSQL_AVAILABLE = False


SQL_WHITELIST = re.compile(r"^\s*select\b[\s\S]*$", re.IGNORECASE)
DISALLOWED = [";", "attach", "drop", "alter", "pragma", "vacuum", "insert", "update", "delete"]


def validate_sql(sql: str) -> bool:
    lowered = sql.lower()
    if not SQL_WHITELIST.match(sql):
        return False
    for d in DISALLOWED:
        if d in lowered:
            return False
    if ";" in sql:
        return False
    return True


def get_mysql_config_from_env() -> dict:
    # Use rag_engine.settings as the canonical source
    return settings.get_mysql_config()


def run_sql(db_path_or_config: Any, sql: str, params: List[Any] | None = None, limit: int = 500):
    """Execute a read-only SQL query safely and return rows (limited).

    db_path_or_config may be:
      - a dict with MySQL connection params (host,user,password,database)
      - a path to a SQLite file (existing file)
      - None: in which case MySQL env vars will be used if present
    """
    if not validate_sql(sql):
        raise ValueError("SQL failed validation")

    if params is None:
        params = []

    # ensure LIMIT
    if "limit" not in sql.lower():
        sql = f"{sql.strip()} LIMIT {limit}"

    # If a dict was passed, use MySQL
    if isinstance(db_path_or_config, dict):
        db_conf = db_path_or_config
        if not MYSQL_AVAILABLE:
            raise RuntimeError("mysql-connector-python is not installed")

        conn = mysql.connector.connect(
            host=db_conf.get("host", "localhost"),
            port=int(db_conf.get("port", 3306)),
            user=db_conf.get("user"),
            password=db_conf.get("password"),
            database=db_conf.get("database"),
            connection_timeout=10,
        )
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params)
            rows = cur.fetchmany(limit)
            return [dict(r) for r in rows]
        finally:
            cur.close()
            conn.close()

    # If None or env vars are present, try using MySQL from env
    if db_path_or_config is None and os.environ.get("MYSQL_HOST"):
        if not MYSQL_AVAILABLE:
            raise RuntimeError("mysql-connector-python is not installed")
        db_conf = get_mysql_config_from_env()
        conn = mysql.connector.connect(
            host=db_conf.get("host", "localhost"),
            port=int(db_conf.get("port", 3306)),
            user=db_conf.get("user"),
            password=db_conf.get("password"),
            database=db_conf.get("database"),
            connection_timeout=10,
        )
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(sql, params)
            rows = cur.fetchmany(limit)
            return [dict(r) for r in rows]
        finally:
            cur.close()
            conn.close()

    raise RuntimeError("No valid MySQL config provided in argument or environment")


def generate_sql_from_nl(nl: str, schema_hint: str | None = None) -> str:
    """Generate a SQL statement from natural language using LLM if available.

    If LLM is not available, attempt a naive mapping for simple questions.
    """
    # Prefer Hugging Face SQL model if available
    if HF_AVAILABLE and settings.HUGGINGFACE_API_KEY:
        client = InferenceClient(token=settings.HUGGINGFACE_API_KEY)
        prompt = (
            "Given the following database schema and a natural language request, produce a single SQL SELECT statement. "
            "Return only the SQL (no semicolons). Schema:\n" + (schema_hint or "") + "\nRequest:\n" + nl
        )
        params = {"max_new_tokens": 300, "temperature": 0.0}
        from rag_engine.hf_utils import text_generation as hf_text_gen

        resp = hf_text_gen(client, settings.HF_SQL_MODEL, prompt, params)
        # normalize response
        if isinstance(resp, list) and resp and isinstance(resp[0], dict) and "generated_text" in resp[0]:
            sql = resp[0]["generated_text"].strip()
        elif isinstance(resp, dict) and "generated_text" in resp:
            sql = resp["generated_text"].strip()
        else:
            sql = str(resp).strip()

        # cleanup: remove fences and only take first statement
        sql = sql.strip().strip("```").strip().strip('`').strip()
        sql = sql.splitlines()[0].strip()
        return sql

    # If HF is not available, fall through to naive fallbacks below

    # very naive fallbacks
    nl_low = nl.lower()
    if "how many" in nl_low or "count" in nl_low:
        return "SELECT COUNT(*) as count FROM employees"
    if "list" in nl_low or "show" in nl_low or "which" in nl_low:
        return "SELECT * FROM employees"

    raise RuntimeError("No LLM available and cannot parse request")


if __name__ == "__main__":
    # Demo: generate SQL and (optionally) run it against MySQL using env vars
    try:
        sql = generate_sql_from_nl("How many employees are in the Sales department?")
        print("Generated SQL:\n", sql)

        # Example: run against MySQL if env vars configured
        if os.environ.get("MYSQL_HOST"):
            conf = get_mysql_config_from_env()
            try:
                rows = run_sql(conf, sql)
                print("Query rows:", rows)
            except Exception as e:
                print("Query failed:", e)
    except Exception as e:
        print("Demo failed:", e)
