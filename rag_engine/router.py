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
    "Choose `sql` for questions about employee records / HR data held in a "
    "database: salaries, leaves or leave balance, headcount, departments, joining "
    "dates, appraisals, ratings, attrition, promotions, counts, lists, or anything "
    "phrased like 'how many…', 'which department…', 'my salary/leaves/appraisal'.\n"
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
    answer = chat(ROUTE_PROMPT.format(question=question), model=settings.HF_ANSWER_MODEL, max_tokens=4)
    word = answer.strip().lower()
    if "sql" in word:
        return "sql"
    if "rag" in word:
        return "rag"
    return "chat"
