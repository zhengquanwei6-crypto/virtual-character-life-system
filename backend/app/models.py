from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Character(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("char"), primary_key=True)
    code: str = Field(index=True, unique=True)
    status: str = Field(default="draft", index=True)
    version: int = Field(default=1)
    is_default: bool = Field(default=False, index=True)
    profile_id: Optional[str] = Field(default=None, index=True)
    prompt_id: Optional[str] = Field(default=None, index=True)
    visual_id: Optional[str] = Field(default=None, index=True)
    published_at: Optional[datetime] = None


class CharacterProfile(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("profile"), primary_key=True)
    character_id: str = Field(index=True)
    name: str
    avatar_url: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    scenario: Optional[str] = None
    first_message: Optional[str] = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class CharacterPrompt(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("prompt"), primary_key=True)
    character_id: str = Field(index=True)
    system_prompt: str
    roleplay_prompt: str
    conversation_style: Optional[str] = None
    safety_prompt: Optional[str] = None


class CharacterVisual(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("visual"), primary_key=True)
    character_id: str = Field(index=True)
    visual_prompt: str
    visual_negative_prompt: Optional[str] = None
    generation_preset_id: str = Field(index=True)


class GenerationPreset(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("preset"), primary_key=True)
    name: str
    description: Optional[str] = None
    status: str = Field(default="draft", index=True)
    version: int = Field(default=1)
    workflow_template_id: str = Field(index=True)
    checkpoint: str
    loras: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    width: int = Field(default=768)
    height: int = Field(default=1024)
    steps: int = Field(default=24)
    cfg: float = Field(default=7.0)
    sampler: str = Field(default="euler")
    scheduler: Optional[str] = None
    seed_mode: str = Field(default="random")
    seed: Optional[int] = None
    positive_prompt_prefix: Optional[str] = None
    positive_prompt_suffix: Optional[str] = None
    negative_prompt: Optional[str] = None
    activated_at: Optional[datetime] = None


class WorkflowTemplate(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("workflow"), primary_key=True)
    name: str
    description: Optional[str] = None
    status: str = Field(default="draft", index=True)
    version: int = Field(default=1)
    workflow_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    node_mapping_id: Optional[str] = Field(default=None, index=True)


class NodeMapping(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("mapping"), primary_key=True)
    name: str
    description: Optional[str] = None
    status: str = Field(default="draft", index=True)
    version: int = Field(default=1)
    mappings: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class ChatSession(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("session"), primary_key=True)
    character_id: str = Field(index=True)
    title: Optional[str] = None


class ChatMessage(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("msg"), primary_key=True)
    session_id: str = Field(index=True)
    role: str = Field(index=True)
    content: str
    image_task_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    llm_decision: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class ImageTask(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("imgtask"), primary_key=True)
    session_id: Optional[str] = Field(default=None, index=True)
    message_id: Optional[str] = Field(default=None, index=True)
    character_id: str = Field(index=True)
    generation_preset_id: str = Field(index=True)
    workflow_template_id: str = Field(index=True)
    node_mapping_id: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    prompt: str
    negative_prompt: Optional[str] = None
    comfy_prompt_id: Optional[str] = None
    parameter_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    generated_asset_id: Optional[str] = Field(default=None, index=True)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


class GeneratedAsset(SQLModel, table=True):
    id: str = Field(default_factory=lambda: new_id("asset"), primary_key=True)
    image_task_id: str = Field(index=True)
    file_path: str
    public_url: str
    width: int
    height: int
    file_size: int
    format: str
    created_at: datetime = Field(default_factory=utc_now)


class LLMProviderConfig(TimestampMixin, table=True):
    id: str = Field(default="default", primary_key=True)
    enabled: bool = Field(default=False)
    base_url: str = ""
    model: Optional[str] = None
    api_key: Optional[str] = None
    timeout: int = Field(default=60)


class AdminAIConfig(TimestampMixin, table=True):
    id: str = Field(default="default", primary_key=True)
    enabled: bool = Field(default=False)
    base_url: str = ""
    model: Optional[str] = None
    api_key: Optional[str] = None
    timeout: int = Field(default=60)
    temperature: float = Field(default=0.4)
    purpose: str = Field(default="admin", index=True)


class AITask(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("aitask"), primary_key=True)
    type: str = Field(index=True)
    status: str = Field(default="queued", index=True)
    target_type: Optional[str] = Field(default=None, index=True)
    target_id: Optional[str] = Field(default=None, index=True)
    input_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_draft: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    apply_mode: str = Field(default="draft")
    applied_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class CharacterTemplate(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("template"), primary_key=True)
    name: str
    category: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = None
    profile_draft: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    prompt_draft: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    visual_draft: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: str = Field(default="built_in", index=True)


class ComfyResourceCache(TimestampMixin, table=True):
    id: str = Field(default_factory=lambda: new_id("resource"), primary_key=True)
    base_url: str = Field(index=True)
    resource_type: str = Field(index=True)
    items: Any = Field(default_factory=list, sa_column=Column(JSON))
    fetched_at: Optional[datetime] = None
    source: str = Field(default="cache")
    error_code: Optional[str] = None
    error_message: Optional[str] = None
