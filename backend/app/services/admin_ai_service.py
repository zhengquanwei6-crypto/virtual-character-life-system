from __future__ import annotations

import json
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - local environment guard
    httpx = None  # type: ignore[assignment]

from sqlmodel import Session, select

from app.database import engine
from app.models import AdminAIConfig, AITask, Character, CharacterTemplate, NodeMapping, WorkflowTemplate, utc_now
from app.responses import ApiError
from app.schemas import AdminAIConfigUpdate, AITaskCreate
from app.services.character_service import character_bundle
from app.services.llm_service import llm_headers, parse_llm_output


ADMIN_AI_CONFIG_ID = "default"
SUPPORTED_TASK_TYPES = {
    "character.generate",
    "character.optimize",
    "prompt.optimize",
    "visual-prompt.optimize",
    "generation-preset.suggest",
    "workflow.analyze",
    "workflow.mapping-draft",
    "workflow.diagnose",
}


def _mask_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _config_row(session: Session) -> AdminAIConfig | None:
    return session.get(AdminAIConfig, ADMIN_AI_CONFIG_ID)


def admin_ai_config_dto(session: Session) -> dict[str, Any]:
    row = _config_row(session)
    if not row:
        return {
            "enabled": False,
            "baseUrl": "",
            "model": None,
            "timeout": 60,
            "temperature": 0.4,
            "purpose": "admin",
            "source": "database",
            "hasApiKey": False,
            "maskedApiKey": None,
            "notice": "后台 AI 独立于用户聊天模型，用于角色生成、提示词优化和 Workflow 诊断。未启用或外链失效时不会生成虚拟草稿。",
        }
    return {
        "enabled": row.enabled,
        "baseUrl": row.base_url,
        "model": row.model,
        "timeout": row.timeout,
        "temperature": row.temperature,
        "purpose": row.purpose,
        "source": "database",
        "hasApiKey": bool(row.api_key),
        "maskedApiKey": _mask_key(row.api_key),
        "updatedAt": row.updated_at,
        "notice": "后台 AI 独立于用户聊天模型，用于角色生成、提示词优化和 Workflow 诊断。未启用或外链失效时不会生成虚拟草稿。",
    }


def save_admin_ai_config(session: Session, payload: AdminAIConfigUpdate) -> dict[str, Any]:
    row = _config_row(session) or AdminAIConfig()
    incoming_key = payload.apiKey
    if incoming_key is None or incoming_key.strip() in {"", "****", "********"}:
        api_key = row.api_key
    else:
        api_key = incoming_key.strip()

    row.enabled = payload.enabled
    row.base_url = payload.baseUrl.strip().rstrip("/")
    row.model = payload.model.strip() if payload.model else None
    row.api_key = api_key
    row.timeout = max(5, min(int(payload.timeout or 60), 600))
    row.temperature = max(0.0, min(float(payload.temperature or 0.4), 2.0))
    row.purpose = "admin"
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return admin_ai_config_dto(session)


def _require_httpx() -> Any:
    if httpx is None:
        raise ApiError("ADMIN_AI_UNAVAILABLE", "Python package httpx is not installed. Run: pip install -r requirements.txt", 503)
    return httpx


def _effective_config(session: Session) -> dict[str, Any]:
    row = _config_row(session)
    return {
        "enabled": bool(row.enabled) if row else False,
        "baseUrl": (row.base_url if row else "").rstrip("/"),
        "model": row.model if row else None,
        "apiKey": row.api_key if row else None,
        "timeout": row.timeout if row else 60,
        "temperature": row.temperature if row else 0.4,
    }


def admin_ai_models(session: Session) -> dict[str, Any]:
    config = _effective_config(session)
    if not config["enabled"]:
        return {
            "enabled": False,
            "ok": False,
            "mode": "disabled",
            "models": [],
            "errorCode": "ADMIN_AI_DISABLED",
            "message": "后台 AI 未启用，无法生成 AI 草稿。请管理员配置可访问的 OpenAI-compatible 外链与 API Key。",
        }
    if not config["baseUrl"]:
        raise ApiError("ADMIN_AI_UNAVAILABLE", "后台 AI Base URL 为空", 503)
    http = _require_httpx()
    try:
        with http.Client(timeout=min(int(config["timeout"]), 15)) as client:
            response = client.get(f"{config['baseUrl']}/models", headers=llm_headers(config))
            response.raise_for_status()
            payload = response.json()
    except http.TimeoutException as exc:
        raise ApiError("ADMIN_AI_TIMEOUT", "后台 AI 模型列表请求超时", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("ADMIN_AI_UNAVAILABLE", "后台 AI 服务不可用", 503, str(exc)) from exc
    models = payload.get("data", []) if isinstance(payload, dict) else []
    return {"enabled": True, "ok": True, "mode": "live", "baseUrl": config["baseUrl"], "model": config["model"], "models": models}


def _resolve_model(session: Session) -> str:
    config = _effective_config(session)
    if config["model"]:
        return str(config["model"])
    models = admin_ai_models(session).get("models") or []
    model = models[0].get("id") if models and isinstance(models[0], dict) else None
    if not model:
        raise ApiError("ADMIN_AI_UNAVAILABLE", "后台 AI 未找到可用模型", 503)
    return model


def _call_admin_ai(session: Session, messages: list[dict[str, str]], *, temperature: float | None = None) -> str:
    config = _effective_config(session)
    if not config["enabled"]:
        raise ApiError("ADMIN_AI_DISABLED", "后台 AI 未启用", 400)
    model = _resolve_model(session)
    http = _require_httpx()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": config["temperature"] if temperature is None else temperature,
    }
    try:
        with http.Client(timeout=int(config["timeout"])) as client:
            response = client.post(f"{config['baseUrl']}/chat/completions", headers=llm_headers(config), json=payload)
            response.raise_for_status()
            result = response.json()
    except http.TimeoutException as exc:
        raise ApiError("ADMIN_AI_TIMEOUT", "后台 AI 请求超时", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("ADMIN_AI_UNAVAILABLE", "后台 AI 服务不可用", 503, str(exc)) from exc
    return result.get("choices", [{}])[0].get("message", {}).get("content", "")


def test_admin_ai(session: Session, message: str) -> dict[str, Any]:
    config = _effective_config(session)
    if not config["enabled"]:
        return {
            "ok": False,
            "mode": "disabled",
            "errorCode": "ADMIN_AI_DISABLED",
            "message": "后台 AI 未启用，无法测试连接。请管理员配置可访问的 OpenAI-compatible 外链与 API Key。",
        }
    content = _call_admin_ai(
        session,
        [
            {"role": "system", "content": "你是虚拟角色生命系统的后台配置助手。用简洁中文回答。"},
            {"role": "user", "content": message},
        ],
    )
    return {"ok": True, "mode": "live", "reply": content}


def create_ai_task(session: Session, payload: AITaskCreate) -> AITask:
    if payload.type not in SUPPORTED_TASK_TYPES:
        raise ApiError("AI_TASK_TYPE_UNSUPPORTED", "不支持的 AI 任务类型", 400, {"supported": sorted(SUPPORTED_TASK_TYPES)})
    task = AITask(
        type=payload.type,
        status="queued",
        target_type=payload.targetType,
        target_id=payload.targetId,
        input_snapshot=payload.inputSnapshot,
        apply_mode=payload.applyMode if payload.applyMode in {"draft", "overwrite"} else "draft",
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def get_ai_task(session: Session, task_id: str) -> AITask:
    task = session.get(AITask, task_id)
    if not task:
        raise ApiError("AI_TASK_NOT_FOUND", "AI 任务不存在", 404)
    return task


def _json_instruction() -> str:
    return (
        "只返回合法 JSON，不要 markdown。字段必须包含 title、summary、draft、reasons、risks、applicableFields。"
        "draft 中只放可应用配置字段；reasons 和 risks 用中文数组。"
    )


def _build_live_messages(task: AITask) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是虚拟角色生命系统的后台 AI 配置专家，擅长角色设定、提示词优化、ComfyUI Workflow 诊断。"
                "你不会直接覆盖生产配置，只输出草稿、理由、风险和可应用字段。"
                + _json_instruction()
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "taskType": task.type,
                    "targetType": task.target_type,
                    "targetId": task.target_id,
                    "inputSnapshot": task.input_snapshot,
                },
                ensure_ascii=False,
            ),
        },
    ]


def run_ai_task(task_id: str) -> None:
    with Session(engine) as session:
        task = session.get(AITask, task_id)
        if not task:
            return
        task.status = "running"
        task.updated_at = utc_now()
        session.add(task)
        session.commit()
        session.refresh(task)
        try:
            config = _effective_config(session)
            if not config["enabled"]:
                raise ApiError(
                    "ADMIN_AI_DISABLED",
                    "后台 AI 未启用或外链不可访问，请管理员检查后台 AI 外链与 API Key。",
                    503,
                )
            content = _call_admin_ai(session, _build_live_messages(task))
            data = parse_llm_output(content)
            if "draft" not in data:
                raise ApiError("ADMIN_AI_INVALID_OUTPUT", "后台 AI 返回格式无效，没有生成可应用草稿。", 502, {"raw": content})
            task.output_draft = data
            task.status = "succeeded"
            task.error_code = None
            task.error_message = None
        except ApiError as exc:
            task.output_draft = None
            task.status = "failed"
            task.error_code = exc.code
            task.error_message = exc.message
        except Exception as exc:  # pragma: no cover - defensive task boundary
            task.status = "failed"
            task.error_code = "AI_TASK_FAILED"
            task.error_message = str(exc)
        task.updated_at = utc_now()
        session.add(task)
        session.commit()


def apply_ai_task(session: Session, task_id: str, *, overwrite: bool = False) -> dict[str, Any]:
    task = get_ai_task(session, task_id)
    if task.status != "succeeded" or not task.output_draft:
        raise ApiError("AI_TASK_NOT_READY", "AI 草稿尚未生成完成", 400)
    draft = task.output_draft.get("draft") or {}
    applied: dict[str, Any] = {"taskId": task.id, "applied": False, "fields": []}

    if task.target_type == "character" and task.target_id:
        character = session.get(Character, task.target_id)
        if not character:
            raise ApiError("CHARACTER_NOT_FOUND", "角色不存在", 404)
        bundle = character_bundle(session, character)
        profile = bundle["profile"]
        prompt = bundle["prompt"]
        visual = bundle["visual"]

        profile_draft = draft.get("profile") or {}
        prompt_draft = draft.get("prompt") or {}
        visual_draft = draft.get("visual") or {}
        if profile_draft:
            for api_key, attr in {
                "name": "name",
                "avatarUrl": "avatar_url",
                "description": "description",
                "personality": "personality",
                "scenario": "scenario",
                "firstMessage": "first_message",
                "tags": "tags",
            }.items():
                if api_key in profile_draft and (overwrite or getattr(profile, attr, None) in {None, ""}):
                    setattr(profile, attr, profile_draft[api_key])
                    applied["fields"].append(f"profile.{api_key}")
            profile.updated_at = utc_now()
            session.add(profile)
        if prompt_draft:
            for api_key, attr in {
                "systemPrompt": "system_prompt",
                "roleplayPrompt": "roleplay_prompt",
                "conversationStyle": "conversation_style",
                "safetyPrompt": "safety_prompt",
            }.items():
                if api_key in prompt_draft and (overwrite or getattr(prompt, attr, None) in {None, ""}):
                    setattr(prompt, attr, prompt_draft[api_key])
                    applied["fields"].append(f"prompt.{api_key}")
            prompt.updated_at = utc_now()
            session.add(prompt)
        if visual_draft:
            for api_key, attr in {
                "visualPrompt": "visual_prompt",
                "visualNegativePrompt": "visual_negative_prompt",
            }.items():
                if api_key in visual_draft and (overwrite or getattr(visual, attr, None) in {None, ""}):
                    setattr(visual, attr, visual_draft[api_key])
                    applied["fields"].append(f"visual.{api_key}")
            visual.updated_at = utc_now()
            session.add(visual)
        character.version += 1
        character.updated_at = utc_now()
        session.add(character)
        applied["applied"] = True
        applied["target"] = character_bundle(session, character)

    elif task.target_type == "nodeMapping" and task.target_id:
        mapping = session.get(NodeMapping, task.target_id)
        if not mapping:
            raise ApiError("NODE_MAPPING_NOT_FOUND", "NodeMapping 不存在", 404)
        mapping_draft = draft.get("nodeMapping") or draft.get("mappings")
        if not isinstance(mapping_draft, dict):
            raise ApiError("AI_DRAFT_NOT_APPLICABLE", "AI 草稿中没有可应用的 NodeMapping", 400)
        mapping.mappings = mapping_draft
        mapping.version += 1
        mapping.updated_at = utc_now()
        session.add(mapping)
        applied["applied"] = True
        applied["fields"].append("mappings")
        applied["target"] = mapping

    else:
        raise ApiError("AI_DRAFT_NOT_APPLICABLE", "该 AI 草稿没有绑定可应用目标，请在页面中手动确认。", 400)

    task.apply_mode = "overwrite" if overwrite else "draft"
    task.applied_at = utc_now()
    task.updated_at = utc_now()
    session.add(task)
    session.commit()
    session.refresh(task)
    return applied


def list_character_templates(session: Session) -> list[CharacterTemplate]:
    return session.exec(select(CharacterTemplate).order_by(CharacterTemplate.category, CharacterTemplate.created_at)).all()
