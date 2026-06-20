"""Chatbot endpoints: ask questions, browse conversation history, suggestions."""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

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
        "Which department has the highest leave utilization?",
        "What does the code of conduct policy say about gifts?",
        "How many employees are in the Sales department?",
    ],
}


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest, user: Dict[str, Any] = Depends(get_current_user)) -> ChatResponse:
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
