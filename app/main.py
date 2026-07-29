"""Orbis HR Compliance Co-pilot — FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload
Docs at:   http://localhost:8000/docs
"""
import logging
import os
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_policy_files()
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
