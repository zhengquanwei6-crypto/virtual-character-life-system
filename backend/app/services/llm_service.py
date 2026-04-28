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
from app.services.llm_config_service import effective_llm_config


def require_httpx() -> Any:
    if httpx is None:
        raise ApiError(
            "LLM_UNAVAILABLE",
            "Python package httpx is not installed. Run: pip install -r requirements.txt",
            503,
        )
    return httpx


def llm_headers(config: dict[str, Any]) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.get("apiKey"):
        headers["Authorization"] = f"Bearer {config['apiKey']}"
    return headers


def llm_health(session: Session | None = None) -> dict[str, Any]:
    settings = get_settings()
    config = effective_llm_config(session)
    if not config["enabled"]:
        return {
            "enabled": False,
            "ok": True,
            "baseUrl": config["baseUrl"],
            "model": config["model"],
            "models": [],
            "source": config["source"],
        }
    if not config["baseUrl"]:
        raise ApiError("LLM_UNAVAILABLE", "LLM base URL is empty", 503)

    http = require_httpx()
    health_timeout = min(int(config["timeout"] or settings.llm_timeout), 8)
    try:
        with http.Client(timeout=health_timeout) as client:
            response = client.get(f"{config['baseUrl']}/models", headers=llm_headers(config))
            response.raise_for_status()
            payload = response.json()
    except http.TimeoutException as exc:
        raise ApiError("LLM_TIMEOUT", "LLM request timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("LLM_UNAVAILABLE", "LLM service is unavailable", 503, str(exc)) from exc

    models = payload.get("data", []) if isinstance(payload, dict) else []
    selected = config["model"] or (models[0].get("id") if models else None)
    return {
        "enabled": True,
        "ok": True,
        "baseUrl": config["baseUrl"],
        "model": selected,
        "models": models,
        "source": config["source"],
    }


def resolve_llm_model(session: Session | None = None) -> str:
    health = llm_health(session)
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

    if not isinstance(data, dict):
        return {
            "replyText": text,
            "shouldGenerateImage": False,
            "imagePrompt": None,
            "errorCode": "LLM_INVALID_OUTPUT",
        }
    return data


def call_chat_completion(
    session: Session | None,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
) -> str:
    settings = get_settings()
    config = effective_llm_config(session)
    if not config["enabled"]:
        raise ApiError("LLM_DISABLED", "LLM is disabled", 400)
    model = resolve_llm_model(session)
    payload = {"model": model, "messages": messages, "temperature": temperature}
    http = require_httpx()
    try:
        with http.Client(timeout=int(config["timeout"] or settings.llm_timeout)) as client:
            response = client.post(
                f"{config['baseUrl']}/chat/completions",
                headers=llm_headers(config),
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except http.TimeoutException as exc:
        raise ApiError("LLM_TIMEOUT", "LLM request timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("LLM_UNAVAILABLE", "LLM service is unavailable", 503, str(exc)) from exc
    return result.get("choices", [{}])[0].get("message", {}).get("content", "")


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


def generate_chat_decision(
    session: Session,
    session_id: str,
    character_prompt: CharacterPrompt,
    user_content: str,
) -> dict[str, Any]:
    config = effective_llm_config(session)
    if not config["enabled"]:
        return mock_llm_decision(user_content)

    content = call_chat_completion(
        session,
        build_llm_messages(character_prompt, recent_chat_context(session, session_id), user_content),
    )
    if not content:
        return {
            "replyText": "",
            "shouldGenerateImage": False,
            "imagePrompt": None,
            "errorCode": "LLM_INVALID_OUTPUT",
        }
    data = parse_llm_output(content)
    if "replyText" not in data or "shouldGenerateImage" not in data:
        return {
            "replyText": content,
            "shouldGenerateImage": False,
            "imagePrompt": None,
            "errorCode": "LLM_INVALID_OUTPUT",
        }
    should_generate = bool(data.get("shouldGenerateImage"))
    image_prompt = data.get("imagePrompt") if should_generate else None
    return {
        "replyText": str(data.get("replyText") or content),
        "shouldGenerateImage": should_generate,
        "imagePrompt": str(image_prompt) if image_prompt else None,
    }


def generate_single_turn_decision(
    character_prompt: CharacterPrompt,
    user_content: str,
    session: Session | None = None,
) -> dict[str, Any]:
    config = effective_llm_config(session)
    if not config["enabled"]:
        return mock_llm_decision(user_content)

    content = call_chat_completion(session, build_llm_messages(character_prompt, [], user_content))
    if not content:
        return {
            "replyText": "",
            "shouldGenerateImage": False,
            "imagePrompt": None,
            "errorCode": "LLM_INVALID_OUTPUT",
        }
    data = parse_llm_output(content)
    if "replyText" not in data or "shouldGenerateImage" not in data:
        return {
            "replyText": content,
            "shouldGenerateImage": False,
            "imagePrompt": None,
            "errorCode": "LLM_INVALID_OUTPUT",
        }
    should_generate = bool(data.get("shouldGenerateImage"))
    image_prompt = data.get("imagePrompt") if should_generate else None
    return {
        "replyText": str(data.get("replyText") or content),
        "shouldGenerateImage": should_generate,
        "imagePrompt": str(image_prompt) if image_prompt else None,
    }


def generate_character_card_with_llm(session: Session | None, seed_text: str, style: str | None = None) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "你是虚拟角色设定师。只返回合法 JSON，不要 markdown。"
                "JSON 字段必须包含 profile、prompt、visual。"
                "profile 包含 name, description, personality, scenario, firstMessage, tags。"
                "prompt 包含 systemPrompt, roleplayPrompt, conversationStyle, safetyPrompt。"
                "visual 包含 visualPrompt, visualNegativePrompt。"
            ),
        },
        {
            "role": "user",
            "content": f"根据这些灵感生成一个中文虚拟角色卡。风格：{style or '温暖、清晰、适合聊天'}。灵感：{seed_text}",
        },
    ]
    content = call_chat_completion(session, messages, temperature=0.85)
    data = parse_llm_output(content)
    if not all(key in data for key in ["profile", "prompt", "visual"]):
        raise ApiError("LLM_INVALID_OUTPUT", "LLM did not return a valid character card", 502, {"raw": content})
    return data
