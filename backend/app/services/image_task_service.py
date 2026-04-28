from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.models import Character, CharacterProfile, CharacterVisual, GeneratedAsset, GenerationPreset, ImageTask, NodeMapping, WorkflowTemplate, utc_now
from app.responses import ApiError
from app.config import get_settings
from app.services.comfyui_service import build_comfy_prompt, poll_history, submit_prompt


ACTIVE_TASK_STATUSES = {"queued", "submitted", "running"}


def task_age_seconds(task: ImageTask) -> float:
    created_at = task.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created_at).total_seconds()


def fail_task(session: Session, task: ImageTask, code: str, message: str) -> ImageTask:
    task.status = "failed"
    task.error_code = code
    task.error_message = message
    task.updated_at = utc_now()
    task.completed_at = task.completed_at or utc_now()
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def compose_positive_prompt(visual: CharacterVisual, preset: GenerationPreset, image_prompt: str) -> str:
    parts = [
        preset.positive_prompt_prefix,
        visual.visual_prompt,
        image_prompt,
        preset.positive_prompt_suffix,
    ]
    return ", ".join([part.strip() for part in parts if part and part.strip()])


def compose_negative_prompt(visual: CharacterVisual, preset: GenerationPreset) -> str | None:
    parts = [preset.negative_prompt, visual.visual_negative_prompt]
    joined = ", ".join([part.strip() for part in parts if part and part.strip()])
    return joined or None


def build_parameter_snapshot(
    character: Character,
    profile: CharacterProfile,
    visual: CharacterVisual,
    preset: GenerationPreset,
    workflow: WorkflowTemplate,
    mapping: NodeMapping,
    llm_image_prompt: str,
    final_positive_prompt: str,
    final_negative_prompt: str | None,
) -> dict[str, Any]:
    seed = preset.seed if preset.seed_mode == "fixed" and preset.seed is not None else random.randint(1, 2_147_483_647)
    comfy_payload = {
        "nodeMapping": mapping.mappings,
        "parameters": {
            "positivePrompt": final_positive_prompt,
            "negativePrompt": final_negative_prompt,
            "checkpoint": preset.checkpoint,
            "loras": preset.loras,
            "width": preset.width,
            "height": preset.height,
            "steps": preset.steps,
            "cfg": preset.cfg,
            "sampler": preset.sampler,
            "scheduler": preset.scheduler,
            "seed": seed,
        },
    }
    comfy_payload["prompt"] = build_comfy_prompt(workflow.workflow_json, mapping.mappings, comfy_payload["parameters"])
    return {
        "character": {
            "id": character.id,
            "version": character.version,
            "profileId": character.profile_id,
            "promptId": character.prompt_id,
            "visualId": character.visual_id,
            "name": profile.name,
            "visualPrompt": visual.visual_prompt,
        },
        "generationPreset": {
            "id": preset.id,
            "version": preset.version,
            "checkpoint": preset.checkpoint,
            "loras": preset.loras,
            "width": preset.width,
            "height": preset.height,
            "steps": preset.steps,
            "cfg": preset.cfg,
            "sampler": preset.sampler,
            "scheduler": preset.scheduler,
            "seed": seed,
            "negativePrompt": final_negative_prompt,
        },
        "workflowTemplate": {
            "id": workflow.id,
            "version": workflow.version,
        },
        "nodeMapping": {
            "id": mapping.id,
            "version": mapping.version,
        },
        "prompts": {
            "llmImagePrompt": llm_image_prompt,
            "finalPositivePrompt": final_positive_prompt,
            "finalNegativePrompt": final_negative_prompt,
        },
        "comfyPayload": comfy_payload,
    }


def create_image_task(
    session: Session,
    character: Character,
    profile: CharacterProfile,
    visual: CharacterVisual,
    image_prompt: str,
    session_id: str | None = None,
    message_id: str | None = None,
    preset_override: GenerationPreset | None = None,
    negative_prompt_override: str | None = None,
) -> ImageTask:
    preset = preset_override or session.get(GenerationPreset, visual.generation_preset_id)
    if not preset:
        raise ApiError("GENERATION_PRESET_NOT_FOUND", "Generation preset not found", 404)
    workflow = session.get(WorkflowTemplate, preset.workflow_template_id)
    if not workflow:
        raise ApiError("WORKFLOW_TEMPLATE_NOT_FOUND", "Workflow template not found", 404)
    if not workflow.node_mapping_id:
        raise ApiError("WORKFLOW_MAPPING_REQUIRED", "Workflow template must bind node mapping", 400)
    mapping = session.get(NodeMapping, workflow.node_mapping_id)
    if not mapping:
        raise ApiError("NODE_MAPPING_NOT_FOUND", "Node mapping not found", 404)

    final_positive_prompt = compose_positive_prompt(visual, preset, image_prompt)
    final_negative_prompt = negative_prompt_override or compose_negative_prompt(visual, preset)
    snapshot = build_parameter_snapshot(
        character,
        profile,
        visual,
        preset,
        workflow,
        mapping,
        image_prompt,
        final_positive_prompt,
        final_negative_prompt,
    )
    settings = get_settings()
    task_status = "queued" if settings.comfyui_enabled else "failed"
    task_error_code = None if settings.comfyui_enabled else "COMFYUI_DISABLED"
    task_error_message = None if settings.comfyui_enabled else "ComfyUI 未启用或外链不可访问，请管理员检查 ComfyUI 外链配置。"
    now = utc_now() if not settings.comfyui_enabled else None
    task = ImageTask(
        session_id=session_id,
        message_id=message_id,
        character_id=character.id,
        generation_preset_id=preset.id,
        workflow_template_id=workflow.id,
        node_mapping_id=mapping.id,
        status=task_status,
        prompt=final_positive_prompt,
        negative_prompt=final_negative_prompt,
        parameter_snapshot=snapshot,
        error_code=task_error_code,
        error_message=task_error_message,
        completed_at=now,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def get_image_task(session: Session, task_id: str) -> ImageTask:
    task = session.get(ImageTask, task_id)
    if not task:
        raise ApiError("IMAGE_TASK_NOT_FOUND", "Image task not found", 404)
    settings = get_settings()
    if settings.comfyui_enabled:
        try:
            progress_comfy_image_task(session, task)
        except ApiError as exc:
            fail_task(session, task, exc.code, exc.message)
    elif task.status == "queued":
        fail_task(
            session,
            task,
            "COMFYUI_DISABLED",
            "ComfyUI 未启用或外链不可访问，请管理员检查 ComfyUI 外链配置。",
        )
    return task


def image_task_detail(session: Session, task: ImageTask) -> dict[str, Any]:
    asset = session.get(GeneratedAsset, task.generated_asset_id) if task.generated_asset_id else None
    return {
        **task.model_dump(),
        "generatedAsset": asset,
    }


def progress_comfy_image_task(session: Session, task: ImageTask) -> ImageTask:
    if task.status in {"succeeded", "failed", "canceled"}:
        return task
    timeout_seconds = max(30, get_settings().image_task_timeout)
    if task.status in ACTIVE_TASK_STATUSES and task_age_seconds(task) > timeout_seconds:
        return fail_task(
            session,
            task,
            "IMAGE_TASK_TIMEOUT",
            f"Image generation timed out after {timeout_seconds} seconds",
        )
    preset = session.get(GenerationPreset, task.generation_preset_id)

    if task.status == "queued":
        submit_prompt(task)
        session.add(task)
        session.commit()
        session.refresh(task)
        return task

    asset = poll_history(task, preset)
    if asset:
        session.add(asset)
        session.commit()
        session.refresh(asset)
        task.status = "succeeded"
        task.generated_asset_id = asset.id
        task.completed_at = utc_now()
    elif task.status == "submitted":
        task.status = "running"
    task.updated_at = utc_now()
    session.add(task)
    session.commit()
    session.refresh(task)
    return task
