"""Natural-language -> SQL for HR data questions.

A hosted LLM generates the SQL, which is validated (read-only SELECT only) and
run against the MySQL HR database with a row limit.
"""
import re
from typing import Any, Dict, List

import mysql.connector

from rag_engine import settings
from rag_engine.llm import chat


SELECT_ONLY = re.compile(r"^\s*select\b", re.IGNORECASE)
DISALLOWED = (
    "attach", "drop", "alter", "pragma", "vacuum",
    "insert", "update", "delete", "grant", "revoke",
)

SCHEMA_HINT = (
    "Table employees(EmployeeID, EmployeeName, Age, Gender, Location, Department, "
    "Role, YearsAtCompany, DateOfJoining, YearsInCurrentRole, EducationLevel, "
    "MonthlySalaryINR, WorkHoursPerWeek, ProjectsHandled, TrainingHoursLastYear, "
    "SickLeavesLastYear, OvertimeHoursLastMonth, ManagerRating, DisciplinaryNotices, "
    "PolicyViolationsLastYear, PerformanceRating, PromotionLast2Years, "
    "ComplianceRiskLevel, AttritionRisk)"
)


def validate_sql(sql: str) -> bool:
    """Allow a single read-only SELECT; reject statements that mutate or chain."""
    lowered = sql.lower()
    return (
        bool(SELECT_ONLY.match(sql))
        and ";" not in sql
        and not any(word in lowered for word in DISALLOWED)
    )


def generate_sql_from_nl(question: str, employee_id: int | None = None) -> str:
    scope = ""
    if employee_id is not None:
        scope = (
            f"\n- The user may ONLY see their own data. The statement MUST include "
            f"`WHERE EmployeeID = {employee_id}` and must not expose other employees."
        )
    prompt = (
        "You convert a question into a single MySQL SELECT statement over this exact "
        "schema (column names are case-sensitive):\n"
        f"{SCHEMA_HINT}\n"
        "Rules:\n"
        "- Use ONLY the column names listed above; never invent columns.\n"
        "- The employee identifier column is `EmployeeID`. The join/hire date is "
        "`DateOfJoining`. There is no appraisal-date column.\n"
        "- If the question references data not in the schema, use the closest valid "
        "columns and ignore the rest.\n"
        "- Return ONLY the SQL: one line, no markdown, no explanation, no semicolon."
        f"{scope}\n\n"
        f"Question: {question}\nSQL:"
    )
    raw = chat(prompt, model=settings.HF_SQL_MODEL, max_tokens=200)
    sql = raw.replace("```sql", "").replace("```", "").strip().strip("`").strip()
    lowered = sql.lower()
    if "select" in lowered:  # drop any stray preamble before the statement
        sql = sql[lowered.index("select"):]
    return sql.split(";")[0].strip()


def is_scoped_to(sql: str, employee_id: int) -> bool:
    """True if the SQL restricts results to the given employee's own records.
    Tolerates `EmployeeID`, `employee_id`, table-qualified forms, and any spacing."""
    normalized = re.sub(r"\s+", "", sql.lower())
    return bool(re.search(rf"employee_?id=(?:'?){employee_id}(?:'?)", normalized))


def run_sql(sql: str, limit: int = 500) -> List[Dict[str, Any]]:
    if not validate_sql(sql):
        raise ValueError("SQL failed validation (read-only SELECT required)")
    if "limit" not in sql.lower():
        sql = f"{sql.rstrip()} LIMIT {limit}"

    conn = mysql.connector.connect(**settings.get_mysql_config(), connection_timeout=10)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql)
        return cur.fetchmany(limit)
    finally:
        conn.close()


if __name__ == "__main__":
    generated = generate_sql_from_nl("How many employees are in the Sales department?")
    print("Generated SQL:", generated)
    print("Rows:", run_sql(generated))
