"""RAG answer generation: retrieve policy chunks, then ask a hosted LLM to
answer using only that context, with inline citations and conversation memory.
"""
import re
from typing import Any, Dict, List, Optional

from rag_engine import settings
from rag_engine.llm import chat
from rag_engine.rag_pipeline import search_policy


PROMPT_TEMPLATE = (
    "You are a helpful HR assistant. Use only the provided context to answer the "
    "question. Cite supporting context inline using square-bracket numbers like "
    "[1], [2].\n\n"
    "{history}Context:\n{context}\n\nQuestion:\n{question}\n\n"
    "Answer concisely. If the answer is not in the context, say "
    "\"I don't know based on the provided documents.\""
)


def build_context(matches: List[Dict[str, Any]]) -> str:
    parts = []
    for i, m in enumerate(matches, start=1):
        excerpt = (m.get("text") or "").replace("\n", " ")[:1000]
        parts.append(f"[{i}] {m.get('source')} (p{m.get('page')}): {excerpt}")
    return "\n\n".join(parts)


# Models differ in how they mark citations: some emit [1], others the
# 【1†L3-L4】 form. Normalising to [1] keeps the answer readable and lets the
# source filter below recognise what was actually cited.
_ALT_CITATION = re.compile(r"【\s*(\d+)\s*[^】]*】")


def normalise_citations(answer: str) -> str:
    return _ALT_CITATION.sub(r"[\1]", answer)


def _cited_only(answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only the retrieved chunks the answer actually cited, so a citation
    list means "this is what the answer rests on". Falls back to the full set
    when the model cited nothing, rather than showing no provenance at all."""
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    return [s for s in sources if s["idx"] in cited] or sources


def _format_history(history: Optional[List[Dict[str, str]]]) -> str:
    if not history:
        return ""
    lines = [f"{m['role'].capitalize()}: {m['content']}" for m in history]
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def answer_question(
    question: str,
    top_k: int = 5,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    matches = search_policy(question, top_k=top_k)["results"]
    context = build_context(matches)
    prompt = PROMPT_TEMPLATE.format(
        history=_format_history(history), context=context, question=question
    )
    answer = normalise_citations(chat(prompt, model=settings.ANSWER_MODEL))
    sources = [
        {
            "idx": i,
            "source": m.get("source"),
            "page": m.get("page"),
            "section": m.get("category"),
            "company": m.get("company"),
            "score": m.get("score"),
        }
        for i, m in enumerate(matches, start=1)
    ]
    retrieval_confidence = max((m.get("score") or 0.0 for m in matches), default=0.0)
    return {
        "question": question,
        "answer": answer,
        "sources": _cited_only(answer, sources),
        # Verification runs against everything retrieved, not just what was cited.
        "context": context,
        "retrieval_confidence": retrieval_confidence,
    }


if __name__ == "__main__":
    print(answer_question("What does the company policy say about code of conduct?", top_k=3))
