from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.config import get_settings
from app.models import LLMProviderConfig, utc_now
from app.schemas import LLMConfigUpdate


DEFAULT_CONFIG_ID = "default"


def _mask_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def get_llm_config_row(session: Session) -> LLMProviderConfig | None:
    return session.get(LLMProviderConfig, DEFAULT_CONFIG_ID)


def effective_llm_config(session: Session | None = None) -> dict[str, Any]:
    settings = get_settings()
    config = {
        "enabled": settings.llm_enabled,
        "baseUrl": settings.llm_base_url,
        "model": settings.llm_model or None,
        "apiKey": settings.llm_api_key or None,
        "timeout": settings.llm_timeout,
        "source": "env",
    }
    if session:
        row = get_llm_config_row(session)
        if row:
            config.update(
                {
                    "enabled": row.enabled,
                    "baseUrl": row.base_url.rstrip("/"),
                    "model": row.model or None,
                    "apiKey": row.api_key or None,
                    "timeout": row.timeout or settings.llm_timeout,
                    "source": "database",
                }
            )
    return config


def llm_config_dto(session: Session) -> dict[str, Any]:
    config = effective_llm_config(session)
    return {
        "enabled": config["enabled"],
        "baseUrl": config["baseUrl"],
        "model": config["model"],
        "timeout": config["timeout"],
        "source": config["source"],
        "hasApiKey": bool(config.get("apiKey")),
        "maskedApiKey": _mask_key(config.get("apiKey")),
        "codexNotice": "Codex/ChatGPT Plus 可用于开发工具登录，但不能作为本应用后端的生产 LLM API 额度来源。",
    }


def save_llm_config(session: Session, payload: LLMConfigUpdate) -> dict[str, Any]:
    row = get_llm_config_row(session)
    if not row:
        row = LLMProviderConfig()

    current_key = row.api_key
    incoming_key = payload.apiKey
    if incoming_key is None:
        api_key = current_key
    elif incoming_key.strip() in {"", "********", "****"}:
        api_key = current_key
    else:
        api_key = incoming_key.strip()

    row.enabled = payload.enabled
    row.base_url = payload.baseUrl.strip().rstrip("/")
    row.model = payload.model.strip() if payload.model else None
    row.api_key = api_key
    row.timeout = max(5, min(int(payload.timeout or 60), 600))
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return llm_config_dto(session)
