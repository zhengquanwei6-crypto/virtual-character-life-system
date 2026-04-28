from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Character, GenerationPreset, NodeMapping, WorkflowTemplate
from app.responses import ApiError
from app.responses import api_success
from app.schemas import (
    CharacterUpsert,
    GenerateCardRequest,
    GenerationPresetUpsert,
    LLMConfigTestRequest,
    LLMConfigUpdate,
    NodeMappingUpsert,
    NodeMappingValidateRequest,
    TestChatRequest,
    TestGenerationPresetRequest,
    TestImageRequest,
    WorkflowAnalyzeRequest,
    WorkflowTemplateUpsert,
)
from app.services.admin_service import (
    activate_generation_preset,
    create_generation_preset,
    create_node_mapping,
    create_workflow_template,
    update_generation_preset,
    update_node_mapping,
    update_workflow_template,
    validate_node_mapping,
    validate_workflow_template,
)
from app.services.character_service import (
    character_bundle,
    create_character,
    get_default_character,
    get_character,
    publish_character,
    update_character,
)
from app.services.comfyui_service import comfyui_health
from app.services.llm_config_service import llm_config_dto, save_llm_config
from app.services.llm_service import (
    generate_character_card_with_llm,
    generate_single_turn_decision,
    llm_health,
)
from app.services.image_task_service import create_image_task
from app.services.workflow_analysis_service import analyze_workflow


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/system/llm-health")
def llm_health_api(session: Session = Depends(get_session)):
    return api_success(llm_health(session))


@router.get("/system/comfyui-health")
def comfyui_health_api():
    return api_success(comfyui_health())


@router.get("/llm-config")
def get_llm_config_api(session: Session = Depends(get_session)):
    return api_success(llm_config_dto(session))


@router.put("/llm-config")
def update_llm_config_api(payload: LLMConfigUpdate, session: Session = Depends(get_session)):
    return api_success(save_llm_config(session, payload))


@router.get("/llm-config/models")
def list_llm_models_api(session: Session = Depends(get_session)):
    return api_success(llm_health(session))


@router.post("/llm-config/test")
def test_llm_config_api(payload: LLMConfigTestRequest, session: Session = Depends(get_session)):
    class Prompt:
        system_prompt = "你是虚拟角色生命系统后台的配置助手。"
        roleplay_prompt = "请用简洁中文回答，并说明模型连接是否正常。"

    return api_success(generate_single_turn_decision(Prompt(), payload.message, session))


@router.get("/characters")
def list_characters_api(session: Session = Depends(get_session)):
    characters = session.exec(select(Character).order_by(Character.created_at)).all()
    return api_success([character_bundle(session, character) for character in characters])


@router.post("/characters")
def create_character_api(payload: CharacterUpsert, session: Session = Depends(get_session)):
    return api_success(create_character(session, payload))


@router.put("/characters/{character_id}")
def update_character_api(character_id: str, payload: CharacterUpsert, session: Session = Depends(get_session)):
    return api_success(update_character(session, character_id, payload))


@router.post("/characters/generate-card")
def generate_card_api(payload: GenerateCardRequest, session: Session = Depends(get_session)):
    try:
        return api_success(generate_character_card_with_llm(session, payload.seedText, payload.style))
    except ApiError as exc:
        if exc.code not in {"LLM_DISABLED", "LLM_INVALID_OUTPUT", "LLM_UNAVAILABLE", "LLM_TIMEOUT"}:
            raise
    style = payload.style or "warm virtual companion"
    return api_success(
        {
            "profile": {
                "name": "Mock Character",
                "description": f"A {style} inspired by: {payload.seedText}",
                "personality": "curious, friendly, emotionally vivid",
                "scenario": "A virtual character chats with the user and imagines scenes.",
                "firstMessage": "Hello, I am ready to chat with you.",
                "tags": ["mock", "generated"],
            },
            "prompt": {
                "systemPrompt": "You are a roleplaying virtual character.",
                "roleplayPrompt": "Stay in character and answer naturally.",
                "conversationStyle": "warm, concise, imaginative",
                "safetyPrompt": "Avoid unsafe or harmful content.",
            },
            "visual": {
                "visualPrompt": "beautiful virtual character, expressive eyes, detailed portrait",
                "visualNegativePrompt": "low quality, blurry, distorted",
            },
        }
    )


@router.post("/characters/{character_id}/test-chat")
def test_chat_api(character_id: str, payload: TestChatRequest, session: Session = Depends(get_session)):
    character = get_character(session, character_id)
    bundle = character_bundle(session, character)
    return api_success(generate_single_turn_decision(bundle["prompt"], payload.message, session))


@router.post("/characters/{character_id}/test-image")
def test_image_api(character_id: str, payload: TestImageRequest, session: Session = Depends(get_session)):
    character = get_character(session, character_id)
    bundle = character_bundle(session, character)
    task = create_image_task(
        session=session,
        character=character,
        profile=bundle["profile"],
        visual=bundle["visual"],
        image_prompt=payload.imagePrompt,
    )
    return api_success(task)


@router.post("/characters/{character_id}/publish")
def publish_character_api(character_id: str, session: Session = Depends(get_session)):
    return api_success(publish_character(session, character_id))


@router.get("/generation-presets")
def list_generation_presets_api(session: Session = Depends(get_session)):
    return api_success(session.exec(select(GenerationPreset).order_by(GenerationPreset.created_at)).all())


@router.post("/generation-presets")
def create_generation_preset_api(payload: GenerationPresetUpsert, session: Session = Depends(get_session)):
    return api_success(create_generation_preset(session, payload))


@router.put("/generation-presets/{preset_id}")
def update_generation_preset_api(
    preset_id: str,
    payload: GenerationPresetUpsert,
    session: Session = Depends(get_session),
):
    return api_success(update_generation_preset(session, preset_id, payload))


@router.post("/generation-presets/{preset_id}/test")
def test_generation_preset_api(
    preset_id: str,
    payload: TestGenerationPresetRequest,
    session: Session = Depends(get_session),
):
    preset = session.get(GenerationPreset, preset_id)
    if not preset:
        raise ApiError("GENERATION_PRESET_NOT_FOUND", "Generation preset not found", 404)
    character = get_default_character(session)
    bundle = character_bundle(session, character)
    task = create_image_task(
        session=session,
        character=character,
        profile=bundle["profile"],
        visual=bundle["visual"],
        image_prompt=payload.positivePrompt,
        preset_override=preset,
        negative_prompt_override=payload.negativePrompt,
    )
    return api_success(task)


@router.post("/generation-presets/{preset_id}/activate")
def activate_generation_preset_api(preset_id: str, session: Session = Depends(get_session)):
    return api_success(activate_generation_preset(session, preset_id))


@router.get("/workflow-templates")
def list_workflow_templates_api(session: Session = Depends(get_session)):
    return api_success(session.exec(select(WorkflowTemplate).order_by(WorkflowTemplate.created_at)).all())


@router.post("/workflow-templates/analyze")
def analyze_workflow_template_api(payload: WorkflowAnalyzeRequest):
    return api_success(analyze_workflow(payload.workflowJson))


@router.post("/workflow-templates")
def create_workflow_template_api(payload: WorkflowTemplateUpsert, session: Session = Depends(get_session)):
    return api_success(create_workflow_template(session, payload))


@router.put("/workflow-templates/{workflow_id}")
def update_workflow_template_api(
    workflow_id: str,
    payload: WorkflowTemplateUpsert,
    session: Session = Depends(get_session),
):
    return api_success(update_workflow_template(session, workflow_id, payload))


@router.post("/workflow-templates/{workflow_id}/validate")
def validate_workflow_template_api(workflow_id: str, session: Session = Depends(get_session)):
    return api_success(validate_workflow_template(session, workflow_id))


@router.get("/node-mappings")
def list_node_mappings_api(session: Session = Depends(get_session)):
    return api_success(session.exec(select(NodeMapping).order_by(NodeMapping.created_at)).all())


@router.post("/node-mappings")
def create_node_mapping_api(payload: NodeMappingUpsert, session: Session = Depends(get_session)):
    return api_success(create_node_mapping(session, payload))


@router.put("/node-mappings/{mapping_id}")
def update_node_mapping_api(mapping_id: str, payload: NodeMappingUpsert, session: Session = Depends(get_session)):
    return api_success(update_node_mapping(session, mapping_id, payload))


@router.post("/node-mappings/{mapping_id}/validate")
def validate_node_mapping_api(
    mapping_id: str,
    payload: NodeMappingValidateRequest | None = Body(default=None),
    session: Session = Depends(get_session),
):
    return api_success(
        validate_node_mapping(
            session,
            mapping_id,
            workflow_json=payload.workflowJson if payload else None,
            workflow_template_id=payload.workflowTemplateId if payload else None,
        )
    )
