"""Local embedding model, exposed as a LangChain Embeddings object.

Embeddings are computed on this machine so policy and employee text never
leaves the network. Only the generative models are called remotely — see
llm.py and answer_generator.py.

`HuggingFaceEmbeddings` wraps the same sentence-transformers model the project
has always used; going through LangChain means the vector store and any future
retriever can consume it directly, rather than each caller handling vectors
itself.
"""
import logging
import time
from functools import lru_cache
from typing import List

from rag_engine.settings import EMBEDDING_MODEL_NAME

logger = logging.getLogger("orbis.embeddings")


@lru_cache(maxsize=1)
def get_embeddings():
    """The shared embedding model, loaded once per process.

    Loading takes about fifteen seconds, so it is cached for the process
    lifetime and warmed at startup — otherwise the first policy question pays
    the whole cost and looks like a hang.
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    started = time.perf_counter()
    # Once the weights are on disk there is nothing to fetch, and checking the
    # Hub anyway costs about ten seconds and a network dependency the rest of
    # the retrieval path does not have.
    for local_only in (True, False):
        try:
            model = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL_NAME,
                model_kwargs={"local_files_only": local_only},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info(
                "Embedding model %s ready in %.1fs (%s)",
                EMBEDDING_MODEL_NAME, time.perf_counter() - started,
                "local cache" if local_only else "downloaded",
            )
            return model
        except Exception:
            if local_only:
                continue  # not cached yet — fall through and fetch it
            raise


def warm_up() -> None:
    """Force the model into memory. Called at startup so no request waits on it."""
    embed_query("warm up")


def embed_texts(texts: List[str]) -> List[List[float]]:
    return get_embeddings().embed_documents(texts)


def embed_query(query: str) -> List[float]:
    return get_embeddings().embed_query(query)
