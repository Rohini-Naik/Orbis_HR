"""Chat orchestration: route the question, run the right engine, verify the
answer, persist conversation memory, and write the audit trail.
"""
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.db import execute, query_all, query_one
from app.services import audit_service
from rag_engine import router, settings, verifier
from rag_engine.answer_generator import answer_question
from rag_engine.llm import converse
from rag_engine.nl_to_sql import generate_sql_from_nl, is_scoped_to, run_sql

HISTORY_TURNS = 6  # recent messages fed back as memory
NOT_FOUND = "I don't know based on the provided documents."
SCOPE_DENIED = "I can only provide information about your own records."
GENERAL_SYSTEM = (
    "You are Orbis, a friendly on-premise HR assistant. Reply conversationally and "
    "concisely. You can answer company HR policy questions and an employee's own HR "
    "data questions. If the user asks what you can do, briefly say so and invite a "
    "question. Do not invent policy details or employee data in casual chat."
)


def _ensure_conversation(user: Dict[str, Any], conversation_id: Optional[int], question: str) -> int:
    if conversation_id is None:
        return execute(
            "INSERT INTO conversations (user_id, title) VALUES (%s, %s)",
            (user["id"], question[:60]),
        )
    owns = query_one(
        "SELECT 1 AS ok FROM conversations WHERE id = %s AND user_id = %s",
        (conversation_id, user["id"]),
    )
    if owns is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation_id


def _recent_history(conversation_id: int) -> List[Dict[str, str]]:
    rows = query_all(
        "SELECT role, content FROM messages WHERE conversation_id = %s "
        "ORDER BY id DESC LIMIT %s",
        (conversation_id, HISTORY_TURNS),
    )
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _add_message(conversation_id: int, role: str, content: str) -> None:
    execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
        (conversation_id, role, content),
    )


def _handle_sql(question: str, user: Dict[str, Any]) -> Dict[str, Any]:
    employee_id = user["employee_id"] if user["role"] == "employee" else None

    # A normal user with no linked HR record cannot be safely scoped.
    if user["role"] == "employee" and employee_id is None:
        return {"answer": SCOPE_DENIED, "sql": None, "rows": None, "blocked": True}

    sql = generate_sql_from_nl(question, employee_id=employee_id)

    # Employees may only ever see their own records.
    if employee_id is not None and not is_scoped_to(sql, employee_id):
        return {"answer": SCOPE_DENIED, "sql": sql, "rows": None, "blocked": True}

    rows = run_sql(sql)
    if not rows:
        answer = "No matching records were found."
    elif len(rows) == 1 and len(rows[0]) == 1:
        answer = f"{next(iter(rows[0].values()))}"
    else:
        answer = f"{len(rows)} record(s) found."
    return {"answer": answer, "sql": sql, "rows": rows, "blocked": False}


def _handle_general(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    messages = [{"role": "system", "content": GENERAL_SYSTEM}, *history, {"role": "user", "content": question}]
    try:
        answer = converse(messages, model=settings.HF_ANSWER_MODEL)
    except Exception:
        answer = "Hi! I'm Orbis. Ask me about a company policy or your HR data and I'll help."
    return {"answer": answer}


def _handle_rag(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    result = answer_question(question, history=history)
    verdict = verifier.verify_answer(result["answer"], result["context"])
    blocked = not verdict["grounded"]
    return {
        "answer": NOT_FOUND if blocked else result["answer"],
        "sources": [] if blocked else result["sources"],
        "confidence": verdict["confidence"],
        "blocked": blocked,
    }


def handle_chat(user: Dict[str, Any], question: str, conversation_id: Optional[int]) -> Dict[str, Any]:
    conversation_id = _ensure_conversation(user, conversation_id, question)
    history = _recent_history(conversation_id)
    _add_message(conversation_id, "user", question)

    started = time.perf_counter()
    route = router.decide_route(question)
    response: Dict[str, Any] = {
        "conversation_id": conversation_id, "route": route,
        "sources": [], "sql": None, "rows": None, "confidence": None,
    }

    if route == "sql":
        outcome = _handle_sql(question, user)
        response.update(answer=outcome["answer"], sql=outcome["sql"], rows=outcome["rows"],
                        hallucination_blocked=outcome["blocked"])
    elif route == "rag":
        outcome = _handle_rag(question, history)
        response.update(answer=outcome["answer"], sources=outcome["sources"],
                        confidence=outcome["confidence"], hallucination_blocked=outcome["blocked"])
    else:  # general conversation
        outcome = _handle_general(question, history)
        response.update(answer=outcome["answer"], hallucination_blocked=False)

    _add_message(conversation_id, "assistant", response["answer"])
    audit_service.log_event(
        "chat", user=user, question=question, route=route,
        sql=response["sql"], sources=response["sources"],
        confidence=response["confidence"],
        latency_ms=int((time.perf_counter() - started) * 1000),
        hallucination_blocked=response["hallucination_blocked"],
    )
    return response


def list_conversations(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    return query_all(
        "SELECT id, title, created_at FROM conversations WHERE user_id = %s "
        "ORDER BY id DESC",
        (user["id"],),
    )


def get_conversation(user: Dict[str, Any], conversation_id: int) -> Dict[str, Any]:
    convo = query_one(
        "SELECT id, title, created_at FROM conversations WHERE id = %s AND user_id = %s",
        (conversation_id, user["id"]),
    )
    if convo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    messages = query_all(
        "SELECT role, content, created_at FROM messages "
        "WHERE conversation_id = %s ORDER BY id",
        (conversation_id,),
    )
    return {**convo, "messages": messages}
