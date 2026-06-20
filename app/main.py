"""Orbis HR Compliance Co-pilot — FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload
Docs at:   http://localhost:8000/docs
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import audit, auth, chat, employees, policies
from app.seed import seed_policy_files, seed_users

# Comma-separated list of allowed frontend origins (Vite dev server by default).
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    seed_users()
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

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(policies.router)
app.include_router(employees.router)
app.include_router(audit.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
