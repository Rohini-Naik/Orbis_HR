from typing import Any, Dict

from rag_engine.answer_generator import answer_question
from rag_engine.nl_to_sql import generate_sql_from_nl, run_sql


SQL_KEYWORDS = [
    "employee",
    "salary",
    "department",
    "hire",
    "count",
    "how many",
    "list",
]


def decide_route(question: str) -> str:
    q = question.lower()
    for k in SQL_KEYWORDS:
        if k in q:
            return "sql"
    return "rag"


def handle_question(question: str, db_path: str | None = None) -> Dict[str, Any]:
    route = decide_route(question)
    if route == "sql":
        if not db_path:
            raise RuntimeError("DB path required for SQL route")
        sql = generate_sql_from_nl(question)
        rows = run_sql(db_path, sql)
        return {"route": "sql", "sql": sql, "rows": rows}

    # default to RAG
    return {"route": "rag", **answer_question(question, top_k=5)}


if __name__ == "__main__":
    print(handle_question("How many employees are in Sales?", db_path="database_data/employees.db"))
