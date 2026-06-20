from typing import List, Dict, Any

from rag_engine import settings


# Hugging Face Inference client availability
HF_AVAILABLE = False
try:
    from huggingface_hub import InferenceClient

    HF_AVAILABLE = True
except Exception:
    HF_AVAILABLE = False

from rag_engine.rag_pipeline import search_policy


PROMPT_TEMPLATE = (
    "You are a helpful assistant. Use only the provided context to answer the question. "
    "Cite supporting context inline using square-bracket numbers like [1], [2].\n\n"
    "Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer concisely. If the answer is not available in the context, say 'I don't know based on the provided documents.'"
)


def build_context(matches: List[Dict[str, Any]]) -> str:
    parts = []
    for i, m in enumerate(matches, start=1):
        excerpt = m.get("text", "").replace("\n", " ")[:1000]
        parts.append(f"[{i}] {m.get('source')} (p{m.get('page')}): {excerpt}")
    return "\n\n".join(parts)


def call_hf_generation(prompt: str, model: str | None = None) -> str:
    if not HF_AVAILABLE:
        raise RuntimeError("huggingface_hub InferenceClient not installed")

    token = settings.HUGGINGFACE_API_KEY
    if not token:
        raise RuntimeError("HUGGINGFACE_API_KEY not set in environment")

    client = InferenceClient(token=token)
    use_model = model or settings.HF_ANSWER_MODEL
    params = {"max_new_tokens": 512, "temperature": 0.0}

    # use compatibility wrapper
    from rag_engine.hf_utils import text_generation as hf_text_gen

    resp = hf_text_gen(client, use_model, prompt, params)

    # normalize response
    if isinstance(resp, list) and resp and isinstance(resp[0], dict) and "generated_text" in resp[0]:
        return resp[0]["generated_text"].strip()
    if isinstance(resp, dict) and "generated_text" in resp:
        return resp["generated_text"].strip()

    return str(resp).strip()


def answer_question(question: str, top_k: int = 5) -> Dict[str, Any]:
    """Search and produce an LLM answer with citations.

    If no LLM is configured, returns the assembled context and raw matches.
    """
    search = search_policy(question, top_k=top_k)
    matches = search.get("results", [])
    context = build_context(matches)

    prompt = PROMPT_TEMPLATE.format(context=context, question=question)

    # Use Hugging Face if configured, otherwise return context for local processing
    if HF_AVAILABLE and settings.HUGGINGFACE_API_KEY:
        try:
            answer = call_hf_generation(prompt, model=settings.HF_ANSWER_MODEL)
        except Exception as exc:
            answer = f"(HF LLM error) {exc}\n\nContext:\n{context}"
    else:
        answer = f"(No LLM configured) Context provided:\n{context}"

    sources = [
        {"idx": i + 1, "id": m.get("id"), "source": m.get("source"), "page": m.get("page")}
        for i, m in enumerate(matches)
    ]

    return {"question": question, "answer": answer, "sources": sources}


if __name__ == "__main__":
    q = "What does the company policy say about code of conduct?"
    print(answer_question(q, top_k=3))
