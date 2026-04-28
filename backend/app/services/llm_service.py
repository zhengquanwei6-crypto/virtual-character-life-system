from __future__ import annotations

import json
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - local environment guard
    httpx = None  # type: ignore[assignment]
from sqlmodel import Session, select

from app.config import get_settings
from app.models import CharacterPrompt, ChatMessage
from app.responses import ApiError
from app.services.chat_rules import mock_llm_decision


def require_httpx() -> Any:
    if httpx is None:
        raise ApiError(
            "LLM_UNAVAILABLE",
            "Python package httpx is not installed. Run: pip install -r requirements.txt",
            503,
        )
    return httpx


def llm_headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    return headers


def llm_health() -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_enabled:
        return {
            "enabled": False,
            "ok": True,
            "baseUrl": settings.llm_base_url,
            "model": settings.llm_model or None,
            "models": [],
        }
    http = require_httpx()
    health_timeout = min(settings.llm_timeout, 8)
    try:
        with http.Client(timeout=health_timeout) as client:
            response = client.get(f"{settings.llm_base_url}/models", headers=llm_headers())
            response.raise_for_status()
            payload = response.json()
    except http.TimeoutException as exc:
        raise ApiError("LLM_TIMEOUT", "LLM request timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("LLM_UNAVAILABLE", "LLM service is unavailable", 503, str(exc)) from exc

    models = payload.get("data", []) if isinstance(payload, dict) else []
    selected = settings.llm_model or (models[0].get("id") if models else None)
    return {
        "enabled": True,
        "ok": True,
        "baseUrl": settings.llm_base_url,
        "model": selected,
        "models": models,
    }


def resolve_llm_model() -> str:
    health = llm_health()
    model = health.get("model")
    if not model:
        raise ApiError("LLM_UNAVAILABLE", "No LLM model is available", 503)
    return model


def recent_chat_context(session: Session, session_id: str, limit: int = 12) -> list[dict[str, str]]:
    messages = list(
        session.exec(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
        ).all()
    )
    selected = messages[-limit:]
    return [
        {
            "role": "assistant" if item.role == "assistant" else "user",
            "content": item.content,
        }
        for item in selected
        if item.role in {"user", "assistant"}
    ]


def build_llm_messages(
    character_prompt: CharacterPrompt,
    context: list[dict[str, str]],
    user_content: str,
) -> list[dict[str, str]]:
    instruction = (
        "Return only valid JSON. Do not wrap it in markdown. "
        "The JSON schema is: "
        '{"replyText":"string","shouldGenerateImage":true_or_false,"imagePrompt":"string_or_empty"}. '
        "You only decide whether an image is needed and describe the scene. "
        "If the user asks to draw, generate, show, see, make a photo, picture, image, or uses Chinese words like "
        "画, 看看, 生成, 照片, 样子, set shouldGenerateImage to true and put a clear visual description in imagePrompt. "
        "Do not choose checkpoint, LoRA, workflow, sampler, steps, CFG, scheduler, seed, or image size."
    )
    messages = [
        {"role": "system", "content": character_prompt.system_prompt},
        {"role": "system", "content": character_prompt.roleplay_prompt},
        {"role": "system", "content": instruction},
    ]
    messages.extend(context)
    if not context or context[-1].get("content") != user_content:
        messages.append({"role": "user", "content": user_content})
    return messages


def parse_llm_output(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                return {
                    "replyText": text,
                    "shouldGenerateImage": False,
                    "imagePrompt": None,
                    "errorCode": "LLM_INVALID_OUTPUT",
                }
        else:
            return {
                "replyText": text,
                "shouldGenerateImage": False,
                "imagePrompt": None,
                "errorCode": "LLM_INVALID_OUTPUT",
            }

    if not isinstance(data, dict) or "replyText" not in data or "shouldGenerateImage" not in data:
        return {
            "replyText": text,
            "shouldGenerateImage": False,
            "imagePrompt": None,
            "errorCode": "LLM_INVALID_OUTPUT",
        }

    should_generate = bool(data.get("shouldGenerateImage"))
    image_prompt = data.get("imagePrompt") if should_generate else None
    return {
        "replyText": str(data.get("replyText") or text),
        "shouldGenerateImage": should_generate,
        "imagePrompt": str(image_prompt) if image_prompt else None,
    }


def generate_chat_decision(
    session: Session,
    session_id: str,
    character_prompt: CharacterPrompt,
    user_content: str,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_enabled:
        return mock_llm_decision(user_content)

    model = resolve_llm_model()
    payload = {
        "model": model,
        "messages": build_llm_messages(character_prompt, recent_chat_context(session, session_id), user_content),
        "temperature": 0.7,
    }
    http = require_httpx()
    try:
        with http.Client(timeout=settings.llm_timeout) as client:
            response = client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers=llm_headers(),
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except http.TimeoutException as exc:
        raise ApiError("LLM_TIMEOUT", "LLM request timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("LLM_UNAVAILABLE", "LLM service is unavailable", 503, str(exc)) from exc

    content = (
        result.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if not content:
        return {
            "replyText": "",
            "shouldGenerateImage": False,
            "imagePrompt": None,
            "errorCode": "LLM_INVALID_OUTPUT",
        }
    return parse_llm_output(content)


def generate_single_turn_decision(character_prompt: CharacterPrompt, user_content: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.llm_enabled:
        return mock_llm_decision(user_content)

    model = resolve_llm_model()
    payload = {
        "model": model,
        "messages": build_llm_messages(character_prompt, [], user_content),
        "temperature": 0.7,
    }
    http = require_httpx()
    try:
        with http.Client(timeout=settings.llm_timeout) as client:
            response = client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers=llm_headers(),
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except http.TimeoutException as exc:
        raise ApiError("LLM_TIMEOUT", "LLM request timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("LLM_UNAVAILABLE", "LLM service is unavailable", 503, str(exc)) from exc
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    return parse_llm_output(content) if content else {
        "replyText": "",
        "shouldGenerateImage": False,
        "imagePrompt": None,
        "errorCode": "LLM_INVALID_OUTPUT",
    }
