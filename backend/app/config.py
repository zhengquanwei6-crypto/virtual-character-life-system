from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def _load_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_ENV_VALUES = _load_env_file()


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, _ENV_VALUES.get(name, default))


def get_bool_env(name: str, default: bool = False) -> bool:
    value = get_env(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    try:
        return int(get_env(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_version: str
    llm_enabled: bool
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    llm_timeout: int
    comfyui_enabled: bool
    comfyui_base_url: str
    comfyui_timeout: int
    image_task_timeout: int


def get_settings() -> Settings:
    return Settings(
        app_version=get_env("APP_VERSION", "0.3.0"),
        llm_enabled=get_bool_env("LLM_ENABLED", False),
        llm_base_url=get_env("LLM_BASE_URL", "").rstrip("/"),
        llm_model=get_env("LLM_MODEL", ""),
        llm_api_key=get_env("LLM_API_KEY", ""),
        llm_timeout=get_int_env("LLM_TIMEOUT", 60),
        comfyui_enabled=get_bool_env("COMFYUI_ENABLED", False),
        comfyui_base_url=get_env("COMFYUI_BASE_URL", "").rstrip("/"),
        comfyui_timeout=get_int_env("COMFYUI_TIMEOUT", 300),
        image_task_timeout=get_int_env("IMAGE_TASK_TIMEOUT", 600),
    )
