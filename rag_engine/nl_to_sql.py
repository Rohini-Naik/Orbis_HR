"""Natural-language -> SQL for HR data questions.

A hosted LLM generates the SQL, which is validated (read-only SELECT only) and
run against the MySQL HR database with a row limit.
"""
import logging
import re
from typing import Any, Dict, List

import mysql.connector

from rag_engine import settings, sql_examples
from rag_engine.llm import chat

logger = logging.getLogger("orbis.nl2sql")


SELECT_ONLY = re.compile(r"^\s*select\b", re.IGNORECASE)
# Whole-word match so a legitimate identifier (e.g. `LastUpdated`) is not
# rejected for merely containing a keyword. `union`/`into` are blocked because
# they can widen a scoped read into a full-table dump.
DISALLOWED = re.compile(
    r"\b(attach|drop|alter|pragma|vacuum|insert|update|delete|grant|revoke|"
    r"union|into|outfile|load_file|sleep|benchmark|information_schema)\b",
    re.IGNORECASE,
)
COMMENT = re.compile(r"--|/\*|#")
# Private contact details are never a legitimate target for a generated query.
PRIVATE_COLUMNS = re.compile(r"\bpersonalemail\b", re.IGNORECASE)

# The real columns. A generated query that names anything else is a
# hallucination and will fail at execution — better to catch it first and
# regenerate than to show the user an error.
COLUMNS = [
    "EmployeeID", "FullName", "Email", "PersonalEmail", "Role", "Department",
    "Location", "DateOfJoining", "ManagerID", "ManagerName",
    "CasualLeaveBalance", "CasualLeaveUsed", "SickLeaveBalance", "SickLeaveUsed",
    "EarnedLeaveBalance", "EarnedLeaveUsed", "LastAppraisalDate",
    "NextAppraisalDate", "POSHTrainingCompleted", "POSHTrainingDate",
    "PerformanceRating", "AnnualCTC_INR", "EmploymentType", "IsAdmin", "Status",
]
_KNOWN = {c.lower() for c in COLUMNS} | {"employees"}

# SQL vocabulary that may legitimately appear as a bare word.
_SQL_WORDS = {
    "select", "from", "where", "and", "or", "not", "as", "by", "group", "order",
    "limit", "offset", "asc", "desc", "distinct", "count", "sum", "avg", "min",
    "max", "round", "year", "month", "day", "date", "now", "curdate", "null",
    "is", "in", "like", "between", "case", "when", "then", "else", "end",
    "coalesce", "ifnull", "if", "datediff", "timestampdiff", "cast", "signed",
    "concat", "upper", "lower", "true", "false", "on", "using", "all", "any",
}
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STRING_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")


def unknown_columns(sql: str) -> List[str]:
    """Identifiers in the statement that are not real columns.

    String literals are stripped first so a value like 'Needs Improvement' is
    not mistaken for a column, and `AS alias` names are excluded because the
    query defines them itself.
    """
    body = _STRING_LITERAL.sub(" ", sql)
    aliases = {m.lower() for m in re.findall(r"\bas\s+([A-Za-z_][A-Za-z0-9_]*)", body, re.I)}
    unknown = []
    for token in _IDENTIFIER.findall(body):
        lowered = token.lower()
        if lowered in _SQL_WORDS or lowered in _KNOWN or lowered in aliases:
            continue
        if lowered not in unknown:
            unknown.append(token)
    return unknown

SCHEMA_HINT = (
    "Table employees(\n"
    # Deliberately no sample value: given one, the model copies it into WHERE
    # clauses as if it were the caller's identity.
    "  EmployeeID VARCHAR (primary key; 'EMP' followed by digits — quote it in SQL),\n"
    "  FullName, Email, PersonalEmail, Role, Department, Location,\n"
    "  DateOfJoining DATE, ManagerID VARCHAR, ManagerName,\n"
    "  CasualLeaveBalance INT, CasualLeaveUsed INT,\n"
    "  SickLeaveBalance INT, SickLeaveUsed INT,\n"
    "  EarnedLeaveBalance INT, EarnedLeaveUsed INT,\n"
    "  LastAppraisalDate DATE, NextAppraisalDate DATE,\n"
    "  POSHTrainingCompleted VARCHAR 'Yes'/'No', POSHTrainingDate DATE,\n"
    "  PerformanceRating VARCHAR e.g. 'Exceeds Expectations'/'Meets Expectations'/"
    "'Needs Improvement',\n"
    "  AnnualCTC_INR INT, EmploymentType VARCHAR 'Full-Time'/'Contract',\n"
    "  IsAdmin VARCHAR 'Yes'/'No', Status VARCHAR 'active'/'exited'\n"
    ")"
)


def validate_sql(sql: str) -> bool:
    """Allow a single read-only SELECT; reject statements that mutate, chain,
    comment out the tail, or read beyond the HR data."""
    return (
        bool(SELECT_ONLY.match(sql))
        and ";" not in sql
        and not DISALLOWED.search(sql)
        and not COMMENT.search(sql)
        and not PRIVATE_COLUMNS.search(sql)
    )


def generate_sql_from_nl(
    question: str,
    employee_id: str | None = None,
    caller_id: str | None = None,
    feedback: str | None = None,
) -> str:
    """Turn a question into a single SELECT.

    `employee_id` restricts the caller to their own row and is enforced
    afterwards by `is_scoped_to`. `caller_id` only says who "me"/"my" refers to;
    it is what lets an administrator ask about themselves while still being able
    to query the whole organisation.
    """
    scope = ""
    if employee_id is not None:
        scope = (
            f"\n- The user may ONLY see their own data. The statement MUST include "
            f"`WHERE EmployeeID = '{employee_id}'` and must not expose other employees."
        )
    elif caller_id is not None:
        scope = (
            f"\n- The person asking is EmployeeID '{caller_id}'. If the question is "
            f"about themselves ('me', 'my', 'I'), filter with "
            f"`WHERE EmployeeID = '{caller_id}'`. If it is about the organisation, "
            f"do not filter by EmployeeID at all."
        )
    demonstrations = sql_examples.render(
        sql_examples.select(question, k=6), me=employee_id or caller_id
    )
    prompt = (
        "You are a MySQL expert. Convert the question into ONE SELECT statement.\n\n"
        f"Schema (column names are case-sensitive):\n{SCHEMA_HINT}\n\n"
        f"Worked examples:\n\n{demonstrations}\n\n"
        "Rules:\n"
        "- Use ONLY columns from the schema. Never invent one.\n"
        "- Exclude departed staff with `Status = 'active'` unless the question is "
        "about former employees.\n"
        "- Never select PersonalEmail.\n"
        "- Return ONLY the SQL: one line, no markdown, no explanation, no semicolon."
        f"{scope}\n\n"
        f"Question: {question}\nSQL:"
    )
    if feedback:
        prompt += (
            f"\n\nYour previous attempt was rejected: {feedback}\n"
            "Write a corrected statement using only real columns."
        )
    raw = chat(prompt, model=settings.SQL_MODEL, max_tokens=400)
    return _clean(raw)


# A generated statement ends where SQL stops looking like SQL. Reasoning-style
# models append commentary after the query, so the statement is cut at the first
# of these rather than assuming the whole reply is SQL.
_SQL_TERMINATORS = ("`", ";", "\n\n")
_PROSE_MARKERS = (
    "\nquestion:", "\nexplanation:", "\nnote:", "\nconstraints:", "\nrules:",
    "\nthis ", "\nthe ", "\ni ", "\nwait", "\ncheck ", "\nlet ", "\noutput:",
)
_SQL_CONTINUATION = (
    "from", "where", "and", "or", "group", "order", "having", "limit", "join",
    "on", "select", "union", "left", "inner", "when", "then", "else", "end",
)


def _clean(raw: str) -> str:
    """Extract just the SELECT statement from a model reply.

    Models differ in how much they say around the answer — fences, restated
    rules, chain-of-thought. Rather than trusting any one format, this keeps the
    text from `select` up to the first thing that cannot be part of the query.
    """
    sql = raw.replace("```sql", "").replace("```", "").strip()
    lowered = sql.lower()
    if "select" in lowered:  # drop any preamble before the statement
        sql = sql[lowered.index("select"):]

    for terminator in _SQL_TERMINATORS:
        if terminator in sql:
            sql = sql.split(terminator)[0]

    lowered = sql.lower()
    for marker in _PROSE_MARKERS:
        if marker in lowered:
            sql = sql[: lowered.index(marker)]
            lowered = sql.lower()

    # Keep wrapped lines only while they still read as SQL.
    lines, kept = sql.splitlines(), []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            break
        if i and not stripped.lower().split()[0].rstrip("(,").isidentifier():
            break
        if i and stripped.lower().split()[0].rstrip("(,") not in _SQL_CONTINUATION:
            break
        kept.append(stripped)
    return " ".join(" ".join(kept).split())


def build_sql(
    question: str,
    employee_id: str | None = None,
    caller_id: str | None = None,
    attempts: int = 2,
) -> str:
    """Generate SQL, retrying once if the model invents a column.

    Catching a hallucinated column here — rather than letting MySQL reject it —
    means the user gets an answer instead of an error, and the retry carries the
    specific mistake back to the model.
    """
    feedback = None
    sql = ""
    for _ in range(max(1, attempts)):
        try:
            sql = generate_sql_from_nl(question, employee_id, caller_id, feedback=feedback)
        except Exception as exc:
            logger.warning("SQL generation attempt failed: %s", exc)
            feedback = "the previous attempt returned nothing; reply with only the SQL"
            continue
        missing = unknown_columns(sql)
        if sql and not missing:
            return sql
        if not sql:
            feedback = "the previous attempt was empty; reply with only the SQL statement"
            continue
        feedback = (
            f"the statement referenced {missing}, which do not exist in the schema"
        )
        logger.warning("Generated SQL used unknown columns %s: %s", missing, sql)
    return sql


def is_scoped_to(sql: str, employee_id: str) -> bool:
    """True only if the statement is a plain single-table read restricted to this
    employee's own row.

    Deliberately strict — a matching `EmployeeID = <id>` on its own is not proof
    of scope, because anything that widens the result set alongside it (OR, JOIN,
    UNION, a sub-select, a second FROM) would still leak other people's records.
    The id must also match in full, so `EMP10011` never satisfies the check for
    `EMP1001`. Anything unrecognised fails closed.
    """
    normalized = re.sub(r"\s+", " ", sql.lower())
    if re.search(r"\b(or|join|union|having)\b|\(\s*select", normalized):
        return False
    if len(re.findall(r"\bfrom\b", normalized)) != 1:
        return False
    # ManagerID also ends in "id", so require the column to be exactly EmployeeID.
    return bool(
        re.search(
            rf"(?<![a-z_])employee_?id\s*=\s*'?{re.escape(str(employee_id).lower())}'?"
            rf"(?![a-z0-9_])",
            normalized,
        )
    )


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
