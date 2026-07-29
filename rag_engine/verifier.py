"""Hallucination filter: check that a generated answer is grounded in the
retrieved context before it is shown to the user.
"""
from typing import Any, Dict

from rag_engine import settings
from rag_engine.llm import chat


VERIFY_PROMPT = (
    "You are a strict fact-checker. Decide whether EVERY claim in the ANSWER is "
    "directly supported by the CONTEXT. Reply with exactly one line in the form "
    "`GROUNDED|<confidence>` or `UNGROUNDED|<confidence>` where confidence is a "
    "number between 0 and 1.\n\n"
    "CONTEXT:\n{context}\n\nANSWER:\n{answer}"
)


def verify_answer(answer: str, context: str) -> Dict[str, Any]:
    """Return {grounded: bool, confidence: float, available: bool}.

    Fails *closed*: if the checker is unreachable we cannot claim the answer is
    grounded, so the caller withholds it rather than presenting an unverified
    answer under a "verified" badge. `available` distinguishes "the checker ran
    and rejected this" from "the checker could not run" — they look the same to
    the user but must not be treated alike in the audit trail.
    """
    try:
        verdict = chat(
            VERIFY_PROMPT.format(context=context, answer=answer),
            model=settings.ANSWER_MODEL,
            max_tokens=64,  # room for a reasoning model to think before answering
        )
        label, _, score = verdict.strip().partition("|")
        grounded = label.strip().upper().startswith("GROUNDED")
        try:
            confidence = max(0.0, min(1.0, float(score.strip())))
        except ValueError:
            confidence = 1.0 if grounded else 0.0
        return {"grounded": grounded, "confidence": round(confidence, 3), "available": True}
    except Exception:
        return {"grounded": False, "confidence": 0.0, "available": False}
