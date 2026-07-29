"""Worked examples for NL->SQL.

A small instruction model follows demonstrations far more reliably than it
follows prose rules: rules accumulate, contradict each other, and get applied
out of context (the word "pending" dragging in a POSH filter, for instance).
Examples show the intended mapping instead of describing it.

`{me}` is substituted with the caller's EmployeeID so first-person examples
teach the pattern without pinning a real identity into the prompt.
"""
from functools import lru_cache
from typing import List, Optional, Tuple

# (question, sql) — chosen to cover each column family and each shape of query
# the assistant actually receives.
EXAMPLES: List[Tuple[str, str]] = [
    # --- personal: leave -----------------------------------------------
    (
        "How many casual leaves do I have left?",
        "SELECT CasualLeaveBalance FROM employees WHERE EmployeeID = '{me}'",
    ),
    (
        "How many leaves do I have pending?",
        "SELECT CasualLeaveBalance, SickLeaveBalance, EarnedLeaveBalance "
        "FROM employees WHERE EmployeeID = '{me}'",
    ),
    (
        "How many sick leaves have I taken this year?",
        "SELECT SickLeaveUsed FROM employees WHERE EmployeeID = '{me}'",
    ),
    # --- personal: dates and profile ------------------------------------
    (
        "When is my next appraisal?",
        "SELECT NextAppraisalDate FROM employees WHERE EmployeeID = '{me}'",
    ),
    (
        "When did I join and when is my next appraisal?",
        "SELECT DateOfJoining, NextAppraisalDate FROM employees WHERE EmployeeID = '{me}'",
    ),
    (
        "Who is my manager?",
        "SELECT ManagerName FROM employees WHERE EmployeeID = '{me}'",
    ),
    (
        "What is my performance rating?",
        "SELECT PerformanceRating FROM employees WHERE EmployeeID = '{me}'",
    ),
    # --- organisation-wide: counts and grouping -------------------------
    (
        "How many employees have pending POSH training?",
        "SELECT COUNT(*) AS pending_posh FROM employees "
        "WHERE Status = 'active' AND POSHTrainingCompleted = 'No'",
    ),
    (
        "Who has not completed POSH training?",
        "SELECT FullName, Department FROM employees "
        "WHERE Status = 'active' AND POSHTrainingCompleted = 'No'",
    ),
    (
        "How many employees are in each department?",
        "SELECT Department, COUNT(*) AS headcount FROM employees "
        "WHERE Status = 'active' GROUP BY Department ORDER BY headcount DESC",
    ),
    (
        "How many employees are in the Sales department?",
        "SELECT COUNT(*) AS headcount FROM employees "
        "WHERE Status = 'active' AND Department = 'Sales'",
    ),
    (
        "Which department has used the most sick leave?",
        "SELECT Department, SUM(SickLeaveUsed) AS total_sick_leave FROM employees "
        "WHERE Status = 'active' GROUP BY Department ORDER BY total_sick_leave DESC LIMIT 1",
    ),
    (
        "List employees whose appraisal is due before 2027-01-01",
        "SELECT FullName, NextAppraisalDate FROM employees "
        "WHERE Status = 'active' AND NextAppraisalDate < '2027-01-01' "
        "ORDER BY NextAppraisalDate",
    ),
    (
        "What is the average annual CTC by department?",
        "SELECT Department, AVG(AnnualCTC_INR) AS average_ctc FROM employees "
        "WHERE Status = 'active' GROUP BY Department",
    ),
    (
        "How many people joined in 2022?",
        "SELECT COUNT(*) AS joiners FROM employees "
        "WHERE Status = 'active' AND YEAR(DateOfJoining) = 2022",
    ),
    (
        "Show the employees reporting to EMP1003",
        "SELECT FullName, Role FROM employees "
        "WHERE Status = 'active' AND ManagerID = 'EMP1003'",
    ),
    (
        "How many contractors do we have?",
        "SELECT COUNT(*) AS contractors FROM employees "
        "WHERE Status = 'active' AND EmploymentType = 'Contract'",
    ),
    (
        "Who are the employees rated Exceeds Expectations?",
        "SELECT FullName, Department FROM employees "
        "WHERE Status = 'active' AND PerformanceRating = 'Exceeds Expectations'",
    ),
]


@lru_cache(maxsize=1)
def _example_vectors() -> List[List[float]]:
    """Embed the example questions once, with the model already loaded for
    policy search — no extra dependency and no extra download."""
    from rag_engine.embeddings import embed_texts

    return embed_texts([question for question, _ in EXAMPLES])


def select(question: str, k: int = 6) -> List[Tuple[str, str]]:
    """The k examples closest to this question.

    Showing the relevant demonstrations rather than all of them keeps the prompt
    short and stops unrelated patterns (a POSH filter, say) from bleeding into
    an answer about leave.
    """
    try:
        from rag_engine.embeddings import embed_query

        query_vector = embed_query(question)
        vectors = _example_vectors()
        # Vectors are normalised, so the dot product is cosine similarity.
        ranked = sorted(
            range(len(EXAMPLES)),
            key=lambda i: -sum(a * b for a, b in zip(query_vector, vectors[i])),
        )
        return [EXAMPLES[i] for i in ranked[:k]]
    except Exception:
        # If the embedder is unavailable, a fixed spread still beats none.
        return EXAMPLES[:k]


def render(examples: List[Tuple[str, str]], me: Optional[str]) -> str:
    """Format examples as Question/SQL pairs, substituting the caller's id."""
    identity = me or "EMP0000"
    lines = []
    for question, sql in examples:
        lines.append(f"Question: {question}\nSQL: {sql.format(me=identity)}")
    return "\n\n".join(lines)
