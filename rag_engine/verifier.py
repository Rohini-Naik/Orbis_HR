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


def _budget_for(prompt: str) -> int:
    """Token ceiling for the verdict, scaled to the amount being checked.

    The reply itself is a dozen tokens, but a reasoning model thinks first and
    that thinking grows with the input. A fixed ceiling silently truncated the
    verdict on longer answers, and a truncated verdict arrives as an empty one —
    which fails closed and withholds a perfectly good answer. `max_tokens` is a
    ceiling rather than a cost, so being generous here is free.
    """
    estimated_input = len(prompt) // 4
    return max(512, min(4096, estimated_input * 2))


def verify_answer(answer: str, context: str) -> Dict[str, Any]:
    """Return {grounded: bool, confidence: float, available: bool}.

    Fails *closed*: if the checker is unreachable we cannot claim the answer is
    grounded, so the caller withholds it rather than presenting an unverified
    answer under a "verified" badge. `available` distinguishes "the checker ran
    and rejected this" from "the checker could not run" — they look the same to
    the user but must not be treated alike in the audit trail.
    """
    prompt = VERIFY_PROMPT.format(context=context, answer=answer)
    try:
        verdict = chat(
            prompt,
            model=settings.VERIFIER_MODEL,
            max_tokens=_budget_for(prompt),
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
