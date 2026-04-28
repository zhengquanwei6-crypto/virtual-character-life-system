from __future__ import annotations

from sqlmodel import Session, select

from app.models import ChatMessage, ChatSession, GeneratedAsset, ImageTask, utc_now
from app.responses import ApiError
from app.services.character_service import character_bundle, get_character, get_default_character
from app.services.image_task_service import create_image_task
from app.services.llm_service import generate_chat_decision


def create_chat_session(session: Session, character_id: str | None = None) -> ChatSession:
    character = get_character(session, character_id) if character_id else get_default_character(session)
    bundle = character_bundle(session, character)
    profile = bundle["profile"]
    chat_session = ChatSession(character_id=character.id, title=f"Chat with {profile.name}")
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return chat_session


def get_chat_session(session: Session, session_id: str) -> ChatSession:
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise ApiError("CHAT_SESSION_NOT_FOUND", "Chat session not found", 404)
    return chat_session


def list_messages(session: Session, session_id: str) -> list[dict]:
    get_chat_session(session, session_id)
    messages = list(
        session.exec(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
        ).all()
    )
    return [chat_message_dto(message, session) for message in messages]


def chat_message_dto(message: ChatMessage, session: Session | None = None) -> dict:
    image_tasks = []
    if session:
        image_tasks = [
            image_task_summary_dto(task, session)
            for task_id in (message.image_task_ids or [])
            if (task := session.get(ImageTask, task_id))
        ]
    return {
        "id": message.id,
        "sessionId": message.session_id,
        "role": message.role,
        "content": message.content,
        "imageTaskIds": message.image_task_ids or [],
        "llmDecision": message.llm_decision,
        "createdAt": message.created_at,
        "imageTasks": image_tasks,
    }


def image_task_summary_dto(task: ImageTask, session: Session | None = None) -> dict:
    asset = session.get(GeneratedAsset, task.generated_asset_id) if session and task.generated_asset_id else None
    return {
        "id": task.id,
        "status": task.status,
        "prompt": task.prompt,
        "negativePrompt": task.negative_prompt,
        "errorCode": task.error_code,
        "errorMessage": task.error_message,
        "generatedAsset": asset,
        "createdAt": task.created_at,
        "updatedAt": task.updated_at,
    }


def send_message(session: Session, session_id: str, content: str) -> dict:
    chat_session = get_chat_session(session, session_id)
    character = get_character(session, chat_session.character_id)
    bundle = character_bundle(session, character)
    profile = bundle["profile"]
    prompt = bundle["prompt"]
    visual = bundle["visual"]

    user_message = ChatMessage(session_id=session_id, role="user", content=content)
    session.add(user_message)
    session.commit()
    session.refresh(user_message)

    decision = generate_chat_decision(session, session_id, prompt, content)
    wants_image = bool(decision.get("shouldGenerateImage"))
    image_prompt = decision.get("imagePrompt") if wants_image else None
    reply_text = decision.get("replyText") or ""
    llm_decision = {
        "shouldGenerateImage": wants_image,
        "imagePrompt": image_prompt,
    }
    if decision.get("errorCode"):
        llm_decision["errorCode"] = decision["errorCode"]
    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=reply_text,
        llm_decision=llm_decision,
    )
    session.add(assistant_message)
    session.commit()
    session.refresh(assistant_message)

    image_tasks: list[ImageTask] = []
    if wants_image and image_prompt:
        task = create_image_task(
            session=session,
            character=character,
            profile=profile,
            visual=visual,
            image_prompt=image_prompt,
            session_id=session_id,
            message_id=assistant_message.id,
        )
        assistant_message.image_task_ids = [task.id]
        session.add(assistant_message)
        session.commit()
        session.refresh(assistant_message)
        image_tasks.append(task)

    chat_session.updated_at = utc_now()
    session.add(chat_session)
    session.commit()
    return {
        "userMessage": chat_message_dto(user_message, session),
        "assistantMessage": chat_message_dto(assistant_message, session),
        "imageTasks": [image_task_summary_dto(task) for task in image_tasks],
    }
