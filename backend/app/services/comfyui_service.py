from __future__ import annotations

import copy
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - local environment guard
    httpx = None  # type: ignore[assignment]

from app.config import BASE_DIR, get_settings
from app.models import GeneratedAsset, GenerationPreset, ImageTask, utc_now
from app.responses import ApiError


GENERATED_DIR = BASE_DIR / "data" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def normalize_comfy_workflow_json(workflow_json: dict[str, Any]) -> dict[str, Any]:
    workflow = copy.deepcopy(workflow_json)
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        if "class_type" not in node and "classType" in node:
            node["class_type"] = node.pop("classType")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        input_aliases = {
            "ckptName": "ckpt_name",
            "samplerName": "sampler_name",
        }
        for source, target in input_aliases.items():
            if target not in inputs and source in inputs:
                inputs[target] = inputs.pop(source)
    return workflow


def require_httpx() -> Any:
    if httpx is None:
        raise ApiError(
            "COMFYUI_UNAVAILABLE",
            "Python package httpx is not installed. Run: pip install -r requirements.txt",
            503,
        )
    return httpx


def comfyui_health() -> dict[str, Any]:
    settings = get_settings()
    if not settings.comfyui_enabled:
        return {
            "enabled": False,
            "ok": True,
            "baseUrl": settings.comfyui_base_url,
            "system": None,
        }
    http = require_httpx()
    health_timeout = min(settings.comfyui_timeout, 8)
    try:
        with http.Client(timeout=health_timeout) as client:
            response = client.get(f"{settings.comfyui_base_url}/system_stats")
            response.raise_for_status()
            payload = response.json()
    except http.TimeoutException as exc:
        raise ApiError("COMFYUI_TIMEOUT", "ComfyUI request timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("COMFYUI_UNAVAILABLE", "ComfyUI service is unavailable", 503, str(exc)) from exc
    return {
        "enabled": True,
        "ok": True,
        "baseUrl": settings.comfyui_base_url,
        "system": payload,
    }


def set_input_path(target: dict[str, Any], input_path: str, value: Any) -> None:
    parts = [part for part in input_path.split(".") if part]
    current: Any = target
    for part in parts[:-1]:
        if isinstance(current, dict):
            current = current.setdefault(part, {})
        else:
            raise ApiError("WORKFLOW_INJECTION_FAILED", f"Invalid input path: {input_path}", 400)
    if not parts or not isinstance(current, dict):
        raise ApiError("WORKFLOW_INJECTION_FAILED", f"Invalid input path: {input_path}", 400)
    current[parts[-1]] = value


def apply_mapping_value(workflow: dict[str, Any], mapping: dict[str, Any], key: str, value: Any) -> None:
    spec = mapping.get(key)
    if not spec or value is None:
        return
    node_id = str(spec.get("nodeId", ""))
    input_path = spec.get("inputPath")
    if not node_id or not input_path or node_id not in workflow:
        raise ApiError("WORKFLOW_INJECTION_FAILED", f"Cannot inject {key}", 400)
    set_input_path(workflow[node_id], input_path, value)


def build_comfy_prompt(
    workflow_json: dict[str, Any],
    node_mapping: dict[str, Any],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    workflow = normalize_comfy_workflow_json(workflow_json)
    for key in [
        "positivePrompt",
        "negativePrompt",
        "checkpoint",
        "width",
        "height",
        "steps",
        "cfg",
        "sampler",
        "scheduler",
        "seed",
    ]:
        apply_mapping_value(workflow, node_mapping, key, parameters.get(key))

    lora_specs = node_mapping.get("loras") or []
    loras = parameters.get("loras") or []
    for index, lora in enumerate(loras):
        if index >= len(lora_specs):
            break
        spec = lora_specs[index]
        node_id = str(spec.get("nodeId", ""))
        if not node_id or node_id not in workflow:
            raise ApiError("WORKFLOW_INJECTION_FAILED", f"Cannot inject lora {index}", 400)
        set_input_path(workflow[node_id], spec["nameInputPath"], lora.get("name"))
        set_input_path(workflow[node_id], spec["strengthModelInputPath"], lora.get("strengthModel"))
        set_input_path(workflow[node_id], spec["strengthClipInputPath"], lora.get("strengthClip"))
    return workflow


def submit_prompt(task: ImageTask) -> ImageTask:
    settings = get_settings()
    prompt = task.parameter_snapshot.get("comfyPayload", {}).get("prompt")
    if not prompt:
        raise ApiError("WORKFLOW_INJECTION_FAILED", "ComfyUI prompt payload is missing", 400)
    http = require_httpx()
    try:
        with http.Client(timeout=settings.comfyui_timeout) as client:
            response = client.post(f"{settings.comfyui_base_url}/prompt", json={"prompt": prompt})
            response.raise_for_status()
            payload = response.json()
    except http.TimeoutException as exc:
        raise ApiError("COMFYUI_TIMEOUT", "ComfyUI request timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("COMFYUI_UNAVAILABLE", "ComfyUI service is unavailable", 503, str(exc)) from exc
    prompt_id = payload.get("prompt_id")
    if not prompt_id:
        raise ApiError("COMFYUI_EXECUTION_FAILED", "ComfyUI did not return prompt_id", 502, payload)
    task.comfy_prompt_id = prompt_id
    task.status = "submitted"
    task.updated_at = utc_now()
    return task


def find_first_output_image(history: dict[str, Any]) -> dict[str, Any] | None:
    for item in history.values():
        status = item.get("status", {}) if isinstance(item, dict) else {}
        if status.get("status_str") == "error":
            raise ApiError("COMFYUI_EXECUTION_FAILED", "ComfyUI execution failed", 502, status)
        outputs = item.get("outputs", {}) if isinstance(item, dict) else {}
        for output in outputs.values():
            images = output.get("images", []) if isinstance(output, dict) else []
            if images:
                return images[0]
    return None


def image_format(filename: str, content_type: str | None) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix:
        return "jpg" if suffix == "jpeg" else suffix
    guessed = mimetypes.guess_extension(content_type or "") or ".png"
    return guessed.lstrip(".")


def png_size(data: bytes) -> tuple[int | None, int | None]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    return None, None


def save_comfy_image(task: ImageTask, image: dict[str, Any], preset: GenerationPreset | None) -> GeneratedAsset:
    settings = get_settings()
    params = {
        "filename": image.get("filename", ""),
        "subfolder": image.get("subfolder", ""),
        "type": image.get("type", "output"),
    }
    http = require_httpx()
    try:
        with http.Client(timeout=settings.comfyui_timeout) as client:
            response = client.get(f"{settings.comfyui_base_url}/view?{urlencode(params)}")
            response.raise_for_status()
            data = response.content
    except http.TimeoutException as exc:
        raise ApiError("COMFYUI_TIMEOUT", "ComfyUI image download timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("COMFYUI_UNAVAILABLE", "ComfyUI image download failed", 503, str(exc)) from exc

    fmt = image_format(params["filename"], response.headers.get("content-type"))
    filename = f"{task.id}.{fmt}"
    file_path = GENERATED_DIR / filename
    file_path.write_bytes(data)
    width, height = png_size(data)
    return GeneratedAsset(
        image_task_id=task.id,
        file_path=str(file_path),
        public_url=f"http://127.0.0.1:8000/generated/{filename}",
        width=width or (preset.width if preset else 0),
        height=height or (preset.height if preset else 0),
        file_size=len(data),
        format=fmt,
    )


def poll_history(task: ImageTask, preset: GenerationPreset | None) -> GeneratedAsset | None:
    if not task.comfy_prompt_id:
        submit_prompt(task)
        return None
    settings = get_settings()
    http = require_httpx()
    try:
        with http.Client(timeout=settings.comfyui_timeout) as client:
            response = client.get(f"{settings.comfyui_base_url}/history/{task.comfy_prompt_id}")
            response.raise_for_status()
            payload = response.json()
    except http.TimeoutException as exc:
        raise ApiError("COMFYUI_TIMEOUT", "ComfyUI history request timed out", 504, str(exc)) from exc
    except http.HTTPError as exc:
        raise ApiError("COMFYUI_UNAVAILABLE", "ComfyUI history is unavailable", 503, str(exc)) from exc

    if not payload:
        task.status = "running"
        task.updated_at = utc_now()
        return None

    image = find_first_output_image(payload)
    if not image:
        task.status = "running"
        task.updated_at = utc_now()
        return None
    return save_comfy_image(task, image, preset)
