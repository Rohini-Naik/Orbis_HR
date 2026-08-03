"""RAG answer generation: retrieve policy chunks, then ask a hosted LLM to
answer using only that context, with inline citations and conversation memory.
"""
import re
from typing import Any, Dict, List, Optional

from rag_engine import settings
from rag_engine.config import DEFAULT_TOP_K
from rag_engine.llm import chat
from rag_engine.rag_pipeline import search_policy


PROMPT_TEMPLATE = (
    "You are an HR assistant. Answer the question using ONLY the numbered "
    "context below.\n\n"
    "Rules:\n"
    "- Every statement you make must be supported by the context. Do not add "
    "detail, figures or timeframes that do not appear there, even if you know "
    "them from elsewhere.\n"
    "- Cite with square brackets after each claim, e.g. [1]. Only use numbers "
    "that appear in the context; never invent a citation number.\n"
    "- Prefer a short, fully supported answer over a longer one that goes "
    "beyond the context.\n"
    "- Earlier conversation is background only; the answer must come from the "
    "context.\n"
    "- If the context does not answer the question, reply exactly: "
    "\"I don't know based on the provided documents.\"\n\n"
    "{history}Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer:"
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


_CITATION = re.compile(r"\[(\d+)\]")


def normalise_citations(answer: str, source_count: int) -> str:
    """Convert alternative citation markers to [n], and drop any that point
    nowhere.

    The 【n†…】 form carries the model's own internal numbering, which does not
    match the numbering given in the context — so it can yield references like
    [11] when only eight sources exist. A marker the reader cannot follow is
    worse than no marker, so out-of-range ones are removed rather than shown.
    """
    def keep(match: "re.Match[str]") -> str:
        index = int(match.group(1))
        return f"[{index}]" if 1 <= index <= source_count else ""

    answer = _ALT_CITATION.sub(keep, answer)
    answer = _CITATION.sub(keep, answer)
    # Tidy the gaps a removed marker leaves behind.
    answer = re.sub(r"[ \t]{2,}", " ", answer)
    answer = re.sub(r"[ \t]+([.,;:])", r"\1", answer)
    return answer.strip()


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
    top_k: int = DEFAULT_TOP_K,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    matches = search_policy(question, top_k=top_k)["results"]
    context = build_context(matches)
    prompt = PROMPT_TEMPLATE.format(
        history=_format_history(history), context=context, question=question
    )
    answer = normalise_citations(
        chat(prompt, model=settings.ANSWER_MODEL), source_count=len(matches)
    )
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
