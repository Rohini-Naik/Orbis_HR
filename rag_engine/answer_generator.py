"""Cited policy answers, as a LangChain Expression Language chain.

Retrieval runs first and the model is instructed to answer only from what came
back, so an answer can be attributed to a page rather than to the model's
memory. The chain is:

    question -> retrieve -> number the context -> prompt -> ChatGroq -> text

Retrieval is done here rather than by a stock retrieval chain because the
similarity scores are needed twice: shown to the reader as relevance, and used
to build the numbered context the citations refer to.
"""
import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from rag_engine import settings
from rag_engine.config import DEFAULT_TOP_K
from rag_engine.rag_pipeline import search_policy

logger = logging.getLogger("orbis.rag")

SYSTEM_PROMPT = (
    "You are an HR assistant. Answer the question using ONLY the numbered "
    "context provided.\n\n"
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
    "\"I don't know based on the provided documents.\""
)

HUMAN_PROMPT = "{history}Context:\n{context}\n\nQuestion:\n{question}"

NOT_FOUND = "I don't know based on the provided documents."

# Models differ in how they mark citations: some emit [1], others the
# 【1†L3-L4】 form, whose number is the model's own internal index rather than
# ours — so it can yield references like [11] when only eight sources exist.
_ALT_CITATION = re.compile(r"【\s*(\d+)\s*[^】]*】")
_CITATION = re.compile(r"\[(\d+)\]")


@lru_cache(maxsize=1)
def get_llm():
    """The answering model. Isolated so provider changes stay in one place."""
    from langchain_groq import ChatGroq

    if settings.LLM_PROVIDER != "groq":
        raise RuntimeError(
            "The answer chain is configured for Groq. Set LLM_PROVIDER=groq, or "
            "extend get_llm() with another LangChain chat model."
        )
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set; required to answer policy questions.")
    return ChatGroq(
        model=settings.ANSWER_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0.0,
        max_tokens=1024,
        reasoning_effort=settings.GROQ_REASONING_EFFORT or None,
    )


@lru_cache(maxsize=1)
def get_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)]
    )


def build_context(matches: List[Dict[str, Any]]) -> str:
    """Number the retrieved chunks so the model has something to cite."""
    return "\n\n".join(
        f"[{i}] {m.get('source')} (p{m.get('page')}): "
        f"{(m.get('text') or '').replace(chr(10), ' ')[:1000]}"
        for i, m in enumerate(matches, start=1)
    )


def _format_history(history: Optional[List[Dict[str, str]]]) -> str:
    if not history:
        return ""
    lines = [f"{m['role'].capitalize()}: {m['content']}" for m in history]
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def normalise_citations(answer: str, source_count: int) -> str:
    """Convert alternative citation markers to [n], and drop any that point
    nowhere — a marker the reader cannot follow is worse than no marker."""
    def keep(match: "re.Match[str]") -> str:
        index = int(match.group(1))
        return f"[{index}]" if 1 <= index <= source_count else ""

    answer = _ALT_CITATION.sub(keep, answer)
    answer = _CITATION.sub(keep, answer)
    answer = re.sub(r"[ \t]{2,}", " ", answer)
    answer = re.sub(r"[ \t]+([.,;:])", r"\1", answer)
    return answer.strip()


def _cited_only(answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only the chunks the answer actually cited, so a citation list means
    "this is what the answer rests on". Falls back to the full retrieval set
    when the model cited nothing, rather than showing no provenance at all."""
    cited = {int(n) for n in _CITATION.findall(answer)}
    return [s for s in sources if s["idx"] in cited] or sources


@lru_cache(maxsize=1)
def get_chain():
    """question + context + history -> prompt -> model -> plain text."""
    return (
        RunnablePassthrough()
        | get_prompt()
        | get_llm()
        | StrOutputParser()
    )


def answer_question(
    question: str,
    top_k: int = DEFAULT_TOP_K,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Retrieve, answer from what was retrieved, and report what was cited."""
    matches = search_policy(question, top_k=top_k)["results"]
    context = build_context(matches)

    raw = get_chain().invoke({
        "question": question,
        "context": context,
        "history": _format_history(history),
    })
    answer = normalise_citations(raw, source_count=len(matches))

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
    return {
        "question": question,
        "answer": answer,
        "sources": _cited_only(answer, sources),
        # Verification runs against everything retrieved, not just what was cited.
        "context": context,
        "retrieval_confidence": max((m.get("score") or 0.0 for m in matches), default=0.0),
    }
