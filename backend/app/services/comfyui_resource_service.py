from __future__ import annotations

from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - local environment guard
    httpx = None  # type: ignore[assignment]

from sqlmodel import Session, select

from app.config import get_settings
from app.models import ComfyResourceCache, utc_now
from app.responses import ApiError


MODEL_FOLDERS = {
    "checkpoints": "checkpoints",
    "loras": "loras",
    "vae": "vae",
}
RESOURCE_TYPES = {
    "checkpoints",
    "loras",
    "vae",
    "embeddings",
    "samplers",
    "schedulers",
    "customNodes",
    "nodeObjectInfo",
    "systemStats",
    "queue",
}


def _require_httpx() -> Any:
    if httpx is None:
        raise ApiError("COMFYUI_UNAVAILABLE", "Python package httpx is not installed. Run: pip install -r requirements.txt", 503)
    return httpx


def _base_url() -> str:
    return get_settings().comfyui_base_url.rstrip("/")


def _cache_row(session: Session, resource_type: str, base_url: str | None = None) -> ComfyResourceCache | None:
    base = base_url if base_url is not None else _base_url()
    return session.exec(
        select(ComfyResourceCache).where(
            ComfyResourceCache.base_url == base,
            ComfyResourceCache.resource_type == resource_type,
        )
    ).first()


def _cache_payload(row: ComfyResourceCache | None, *, source: str | None = None) -> dict[str, Any]:
    if not row:
        return {
            "resourceType": None,
            "items": [],
            "source": "empty",
            "fetchedAt": None,
            "errorCode": None,
            "errorMessage": None,
        }
    return {
        "resourceType": row.resource_type,
        "items": row.items,
        "source": source or row.source,
        "fetchedAt": row.fetched_at,
        "errorCode": row.error_code,
        "errorMessage": row.error_message,
    }


def _save_cache(
    session: Session,
    resource_type: str,
    items: Any,
    *,
    source: str = "live",
    error_code: str | None = None,
    error_message: str | None = None,
) -> ComfyResourceCache:
    base = _base_url()
    row = _cache_row(session, resource_type, base) or ComfyResourceCache(base_url=base, resource_type=resource_type)
    row.items = items
    row.source = source
    row.fetched_at = utc_now() if source == "live" else row.fetched_at
    row.error_code = error_code
    row.error_message = error_message
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _mark_cache_error(session: Session, resource_type: str, code: str, message: str) -> ComfyResourceCache | None:
    row = _cache_row(session, resource_type)
    if row:
        row.source = "cache"
        row.error_code = code
        row.error_message = message
        row.updated_at = utc_now()
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def _client_get(path: str) -> Any:
    settings = get_settings()
    if not settings.comfyui_enabled:
        raise ApiError("COMFYUI_DISABLED", "ComfyUI 未启用，当前只能使用缓存或 Mock。", 400)
    if not settings.comfyui_base_url:
        raise ApiError("COMFYUI_UNAVAILABLE", "ComfyUI Base URL 为空", 503)
    http = _require_httpx()
    try:
        with http.Client(timeout=min(settings.comfyui_timeout, 30)) as client:
            response = client.get(f"{settings.comfyui_base_url.rstrip('/')}{path}")
            response.raise_for_status()
            return response.json()
    except http.TimeoutException as exc:
        raise ApiError("COMFYUI_TIMEOUT", f"ComfyUI 请求 {path} 超时", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("COMFYUI_UNAVAILABLE", f"ComfyUI 请求 {path} 失败", 503, str(exc)) from exc


def _extract_options(schema_value: Any) -> list[str]:
    if not isinstance(schema_value, list) or not schema_value:
        return []
    first = schema_value[0]
    if isinstance(first, list):
        return [str(item) for item in first]
    if isinstance(first, str):
        return [str(item) for item in schema_value if isinstance(item, str)]
    return []


def sampler_options(object_info: dict[str, Any]) -> list[str]:
    ksampler = object_info.get("KSampler") or {}
    required = (ksampler.get("input") or {}).get("required") or {}
    return _extract_options(required.get("sampler_name"))


def scheduler_options(object_info: dict[str, Any]) -> list[str]:
    ksampler = object_info.get("KSampler") or {}
    required = (ksampler.get("input") or {}).get("required") or {}
    return _extract_options(required.get("scheduler"))


def _fetch_live_resources(session: Session) -> dict[str, dict[str, Any]]:
    live: dict[str, dict[str, Any]] = {}
    system_stats = _client_get("/system_stats")
    live["systemStats"] = _cache_payload(_save_cache(session, "systemStats", system_stats))

    try:
        queue = _client_get("/queue")
        live["queue"] = _cache_payload(_save_cache(session, "queue", queue))
    except ApiError as exc:
        live["queue"] = _cache_payload(_mark_cache_error(session, "queue", exc.code, exc.message), source="cache")

    try:
        object_info = _client_get("/object_info")
    except ApiError as exc:
        object_info = {}
        live["nodeObjectInfo"] = _cache_payload(_mark_cache_error(session, "nodeObjectInfo", exc.code, exc.message), source="cache")
    else:
        live["nodeObjectInfo"] = _cache_payload(_save_cache(session, "nodeObjectInfo", object_info))
        live["customNodes"] = _cache_payload(_save_cache(session, "customNodes", sorted(object_info.keys())))
        live["samplers"] = _cache_payload(_save_cache(session, "samplers", sampler_options(object_info)))
        live["schedulers"] = _cache_payload(_save_cache(session, "schedulers", scheduler_options(object_info)))

    for resource_type, folder in MODEL_FOLDERS.items():
        try:
            items = _client_get(f"/models/{folder}")
            if isinstance(items, dict):
                items = items.get("models") or items.get("data") or []
            live[resource_type] = _cache_payload(_save_cache(session, resource_type, items))
        except ApiError as exc:
            live[resource_type] = _cache_payload(_mark_cache_error(session, resource_type, exc.code, exc.message), source="cache")

    try:
        embeddings = _client_get("/embeddings")
        live["embeddings"] = _cache_payload(_save_cache(session, "embeddings", embeddings))
    except ApiError as exc:
        live["embeddings"] = _cache_payload(_mark_cache_error(session, "embeddings", exc.code, exc.message), source="cache")

    return live


def list_cached_resources(session: Session) -> dict[str, Any]:
    base = _base_url()
    rows = session.exec(select(ComfyResourceCache).where(ComfyResourceCache.base_url == base)).all()
    resources = {row.resource_type: _cache_payload(row) for row in rows}
    for resource_type in sorted(RESOURCE_TYPES):
        resources.setdefault(resource_type, {"resourceType": resource_type, "items": [], "source": "empty", "fetchedAt": None})
    return {"baseUrl": base, "resources": resources}


def get_cached_resource(session: Session, resource_type: str) -> dict[str, Any]:
    if resource_type not in RESOURCE_TYPES:
        raise ApiError("COMFYUI_RESOURCE_TYPE_UNSUPPORTED", "不支持的 ComfyUI 资源类型", 400, {"supported": sorted(RESOURCE_TYPES)})
    row = _cache_row(session, resource_type)
    payload = _cache_payload(row)
    payload["resourceType"] = resource_type
    return payload


def refresh_comfy_resources(session: Session) -> dict[str, Any]:
    settings = get_settings()
    if not settings.comfyui_enabled:
        cached = list_cached_resources(session)
        return {
            "enabled": False,
            "ok": False,
            "mode": "disabled",
            "baseUrl": settings.comfyui_base_url,
            "errorCode": "COMFYUI_DISABLED",
            "message": "ComfyUI 未启用或外链不可访问。系统不会使用占位图，请管理员检查 ComfyUI 外链。",
            **cached,
        }
    try:
        resources = _fetch_live_resources(session)
        return {"enabled": True, "ok": True, "mode": "live", "baseUrl": settings.comfyui_base_url, "resources": resources}
    except ApiError as exc:
        cached = list_cached_resources(session)
        return {
            "enabled": True,
            "ok": False,
            "mode": "cache",
            "baseUrl": settings.comfyui_base_url,
            "errorCode": exc.code,
            "errorMessage": exc.message,
            "nextStep": "请检查 ComfyUI 地址、反向代理、网络连通性，再点击刷新资源。",
            **cached,
        }


def comfyui_diagnostics(session: Session) -> dict[str, Any]:
    settings = get_settings()
    cached = list_cached_resources(session)
    diagnostics = {
        "enabled": settings.comfyui_enabled,
        "ok": True,
        "baseUrl": settings.comfyui_base_url,
        "mode": "live" if settings.comfyui_enabled else "mock",
        "system": None,
        "queue": None,
        "resources": cached["resources"],
        "nextStep": None,
    }
    if not settings.comfyui_enabled:
        diagnostics.update(
            {
                "ok": False,
                "mode": "disabled",
                "errorCode": "COMFYUI_DISABLED",
                "errorMessage": "ComfyUI 未启用或外链不可访问。系统不会使用占位图。",
                "nextStep": "请管理员启用 ComfyUI，并确认 VPS 可以访问 COMFYUI_BASE_URL。",
            }
        )
        return diagnostics
    try:
        system = _client_get("/system_stats")
        queue = _client_get("/queue")
        _save_cache(session, "systemStats", system)
        _save_cache(session, "queue", queue)
        diagnostics.update({"system": system, "queue": queue, "resources": list_cached_resources(session)["resources"]})
    except ApiError as exc:
        diagnostics.update(
            {
                "ok": False,
                "mode": "cache",
                "errorCode": exc.code,
                "errorMessage": exc.message,
                "nextStep": "请确认 ComfyUI 可访问，或先使用缓存资源继续编辑配置。",
            }
        )
    return diagnostics


def comfy_object_info(session: Session) -> dict[str, Any]:
    settings = get_settings()
    if settings.comfyui_enabled:
        try:
            object_info = _client_get("/object_info")
            row = _save_cache(session, "nodeObjectInfo", object_info)
            return _cache_payload(row)
        except ApiError:
            pass
    return get_cached_resource(session, "nodeObjectInfo")


def comfy_queue(session: Session) -> dict[str, Any]:
    settings = get_settings()
    if settings.comfyui_enabled:
        try:
            queue = _client_get("/queue")
            row = _save_cache(session, "queue", queue)
            return _cache_payload(row)
        except ApiError:
            pass
    return get_cached_resource(session, "queue")
