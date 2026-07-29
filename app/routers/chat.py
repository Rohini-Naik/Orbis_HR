"""Chatbot endpoints: ask questions, browse conversation history, suggestions."""
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
)
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

SUGGESTED = {
    "employee": [
        "How many casual leaves do I have left?",
        "When did I join and when is my next appraisal?",
        "What is the maternity leave policy?",
        "Can I claim reimbursement for a home office chair?",
    ],
    "admin": [
        "How many employees have pending POSH training?",
        "How many employees are in each department?",
        "What does the code of conduct say about gifts?",
        "Who has not completed POSH training?",
    ],
}


# Each question costs several LLM calls, so cap how fast one account can spend
# them. In-process and per-user; ample for interactive use.
RATE_LIMIT = 30
RATE_WINDOW_S = 60
_recent: Dict[int, Deque[float]] = defaultdict(deque)


def _check_rate_limit(user_id: int) -> None:
    now = time.monotonic()
    hits = _recent[user_id]
    while hits and now - hits[0] > RATE_WINDOW_S:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many questions in a short time — please wait a moment.",
        )
    hits.append(now)


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, user: Dict[str, Any] = Depends(get_current_user)) -> ChatResponse:
    _check_rate_limit(user["id"])
    return ChatResponse(**chat_service.handle_chat(user, body.question, body.conversation_id))


@router.get("/suggested-questions", response_model=List[str])
def suggested_questions(user: Dict[str, Any] = Depends(get_current_user)) -> List[str]:
    return SUGGESTED.get(user["role"], [])


@router.get("/conversations", response_model=List[ConversationSummary])
def conversations(user: Dict[str, Any] = Depends(get_current_user)) -> List[Dict[str, Any]]:
    return chat_service.list_conversations(user)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation(
    conversation_id: int, user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    return chat_service.get_conversation(user, conversation_id)
