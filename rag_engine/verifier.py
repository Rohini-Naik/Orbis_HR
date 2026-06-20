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
    """Return {grounded: bool, confidence: float}. Fails open (grounded, 0.0)
    if the verifier model is unreachable, so the API stays usable."""
    try:
        verdict = chat(
            VERIFY_PROMPT.format(context=context, answer=answer),
            model=settings.HF_ANSWER_MODEL,
            max_tokens=16,
        )
        label, _, score = verdict.strip().partition("|")
        grounded = label.strip().upper().startswith("GROUNDED")
        try:
            confidence = max(0.0, min(1.0, float(score.strip())))
        except ValueError:
            confidence = 1.0 if grounded else 0.0
        return {"grounded": grounded, "confidence": round(confidence, 3)}
    except Exception:
        return {"grounded": True, "confidence": 0.0}
