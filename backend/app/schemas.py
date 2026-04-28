from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    characterId: Optional[str] = None


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1)


class CharacterProfileInput(BaseModel):
    name: str
    avatarUrl: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    scenario: Optional[str] = None
    firstMessage: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class CharacterPromptInput(BaseModel):
    systemPrompt: str
    roleplayPrompt: str
    conversationStyle: Optional[str] = None
    safetyPrompt: Optional[str] = None


class CharacterVisualInput(BaseModel):
    visualPrompt: str
    visualNegativePrompt: Optional[str] = None
    generationPresetId: str


class CharacterUpsert(BaseModel):
    code: str
    profile: CharacterProfileInput
    prompt: CharacterPromptInput
    visual: CharacterVisualInput


class GenerateCardRequest(BaseModel):
    seedText: str
    style: Optional[str] = None


class TestChatRequest(BaseModel):
    message: str


class TestImageRequest(BaseModel):
    imagePrompt: str


class TestGenerationPresetRequest(BaseModel):
    positivePrompt: str
    negativePrompt: Optional[str] = None


class GenerationPresetUpsert(BaseModel):
    name: str
    description: Optional[str] = None
    workflowTemplateId: str
    checkpoint: str
    loras: list[dict[str, Any]] = Field(default_factory=list)
    width: int = 768
    height: int = 1024
    steps: int = 24
    cfg: float = 7.0
    sampler: str = "euler"
    scheduler: Optional[str] = None
    seedMode: str = "random"
    seed: Optional[int] = None
    positivePromptPrefix: Optional[str] = None
    positivePromptSuffix: Optional[str] = None
    negativePrompt: Optional[str] = None


class WorkflowTemplateUpsert(BaseModel):
    name: str
    description: Optional[str] = None
    workflowJson: dict[str, Any]
    nodeMappingId: Optional[str] = None


class NodeMappingUpsert(BaseModel):
    name: str
    description: Optional[str] = None
    mappings: dict[str, Any]


class NodeMappingValidateRequest(BaseModel):
    workflowTemplateId: Optional[str] = None
    workflowJson: Optional[dict[str, Any]] = None


class LLMConfigUpdate(BaseModel):
    enabled: bool = False
    baseUrl: str = ""
    model: Optional[str] = None
    apiKey: Optional[str] = None
    timeout: int = 60


class LLMConfigTestRequest(BaseModel):
    message: str = "你好"


class WorkflowAnalyzeRequest(BaseModel):
    workflowJson: dict[str, Any]


class AdminLoginRequest(BaseModel):
    password: str = Field(min_length=1)
