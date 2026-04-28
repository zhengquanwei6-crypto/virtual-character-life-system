from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.responses import api_success
from app.schemas import ChatMessageCreate, ChatSessionCreate
from app.services.character_service import character_bundle, get_default_character
from app.services.chat_service import create_chat_session, list_messages, send_message
from app.services.image_task_service import get_image_task, image_task_detail


router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/characters/default")
def get_default_character_api(session: Session = Depends(get_session)):
    character = get_default_character(session)
    return api_success(character_bundle(session, character))


@router.post("/chat-sessions")
def create_chat_session_api(payload: ChatSessionCreate | None = None, session: Session = Depends(get_session)):
    return api_success(create_chat_session(session, payload.characterId if payload else None))


@router.get("/chat-sessions/{session_id}/messages")
def list_messages_api(session_id: str, session: Session = Depends(get_session)):
    return api_success(list_messages(session, session_id))


@router.post("/chat-sessions/{session_id}/messages")
def send_message_api(session_id: str, payload: ChatMessageCreate, session: Session = Depends(get_session)):
    return api_success(send_message(session, session_id, payload.content))


@router.get("/image-tasks/{task_id}")
def get_image_task_api(task_id: str, session: Session = Depends(get_session)):
    task = get_image_task(session, task_id)
    return api_success(image_task_detail(session, task))
