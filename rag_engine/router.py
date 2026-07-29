"""Route a message to one of three engines:

- `sql`  : questions about employee/HR data that live in the database
- `rag`  : questions about company policies / rules / handbook
- `chat` : general conversation, greetings, small talk, or capability questions

The LLM makes the decision for the highest classification accuracy.
"""
from rag_engine import settings
from rag_engine.llm import chat

ROUTE_PROMPT = (
    "You are the intent router for an HR assistant called Orbis. Read the user "
    "message and reply with EXACTLY ONE word — `sql`, `rag`, or `chat` — and "
    "nothing else.\n\n"
    # The list mirrors the employees table: a router that does not know a field
    # exists sends the question to the wrong engine.
    "Choose `sql` for questions about employee records held in the HR database — "
    "anything answerable by looking a person or a group up:\n"
    "  · leave balances and leave taken (casual, sick, earned)\n"
    "  · appraisal dates, performance ratings, salary or CTC\n"
    "  · joining dates, tenure, employment type (full-time / contract)\n"
    "  · manager, reporting line, who reports to whom, team members\n"
    "  · department, role, location, headcount, POSH training status\n"
    "  · anything phrased 'how many…', 'who is/are…', 'which department…', "
    "'list…', or about 'my' record.\n"
    "Choose `rag` for questions about company policy, rules, handbook, benefits, "
    "code of conduct, eligibility or processes (e.g. 'what is the maternity policy', "
    "'can I claim reimbursement for a chair', 'disciplinary procedure').\n"
    "Choose `chat` for greetings, thanks, small talk, or questions about the "
    "assistant itself (e.g. 'hi', 'how are you', 'who are you', 'what can you do', "
    "'help') — anything that is NOT about HR data or company policy.\n\n"
    "Message: {question}\nAnswer:"
)


def decide_route(question: str) -> str:
    """Return 'sql', 'rag', or 'chat' as classified by the LLM."""
    # Not 4 tokens: a reasoning model spends its budget thinking before it
    # writes anything and would return nothing at all. The reply is matched by
    # substring, so a generous ceiling costs nothing.
    answer = chat(
        ROUTE_PROMPT.format(question=question),
        model=settings.ROUTER_MODEL,
        max_tokens=32,
    )
    word = answer.strip().lower()
    if "sql" in word:
        return "sql"
    if "rag" in word:
        return "rag"
    return "chat"
