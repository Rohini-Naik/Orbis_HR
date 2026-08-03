"""Orbis HR Compliance Co-pilot — FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload
Docs at:   http://localhost:8000/docs
"""
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("orbis")

from app.db import init_db
from app.routers import audit, auth, chat, employees, policies, users
from app.seed import seed_policy_files

# Comma-separated list of allowed frontend origins (Vite dev server by default).
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")


def _warm_embedding_model() -> None:
    """Load the embedding model in the background as the server starts.

    It takes roughly 15 seconds and is then cached for the life of the process.
    Without this the first policy question pays the entire cost — long enough
    that people assume the answer has failed and reload the page, which is
    exactly when it starts working, because the model finished loading anyway.

    Loading on a thread keeps startup immediate; by the time anyone has signed
    in and typed a question, the model is ready.
    """
    def load() -> None:
        try:
            from rag_engine.embeddings import warm_up
            warm_up()
            logger.info("Policy search is ready")
        except Exception:
            logger.exception("Could not preload the embedding model; the first "
                             "policy question will load it instead")

    threading.Thread(target=load, name="embedding-warmup", daemon=True).start()


def _check_index_is_current() -> None:
    """Warn when a policy document on disk has never been indexed.

    Policy PDFs are in version control but the index is not — it is generated.
    So pulling new documents leaves them invisible to search, and the failure is
    silent: the app starts, answers questions, and simply never mentions the new
    policy. Saying so at startup turns that into an obvious instruction.
    """
    try:
        from rag_engine import vector_store
        from rag_engine.config import POLICY_DOCUMENTS_DIR
        from rag_engine.document_loader import SUPPORTED_EXTENSIONS

        if not POLICY_DOCUMENTS_DIR.exists():
            return
        on_disk = {
            p.name for p in POLICY_DOCUMENTS_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        }
        missing = sorted(n for n in on_disk if vector_store.count_by_source(n) == 0)
        if missing:
            logger.warning(
                "%d policy document(s) are not in the search index and cannot be "
                "found by the assistant: %s. Run:  python -m rag_engine.maintenance",
                len(missing), ", ".join(missing),
            )
    except Exception:
        logger.debug("Could not check the policy index", exc_info=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_policy_files()
    _check_index_is_current()
    _warm_embedding_model()
    yield


app = FastAPI(
    title="Orbis HR Compliance Co-pilot",
    description="Agentic AI HR assistant: cited policy answers (RAG) and HR data answers (NL->SQL).",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Turn any unexpected failure into a JSON 500.

    Without this the error escapes before the CORS middleware can label the
    response, so the browser reports only "Network Error" and the real cause is
    visible solely in the server log. The message stays generic — the traceback
    is logged, not sent.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Something went wrong on the server. Please try again."},
    )


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(policies.router)
app.include_router(employees.router)
app.include_router(users.router)
app.include_router(audit.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
