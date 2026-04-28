from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Character, GenerationPreset, NodeMapping, WorkflowTemplate
from app.responses import ApiError
from app.responses import api_success
from app.schemas import (
    CharacterUpsert,
    AdminAIConfigUpdate,
    AITaskApplyRequest,
    AITaskCreate,
    ComfyResourceRefreshRequest,
    GenerateCardRequest,
    GenerationPresetUpsert,
    LLMConfigTestRequest,
    LLMConfigUpdate,
    NodeMappingUpsert,
    NodeMappingValidateRequest,
    TestChatRequest,
    TestGenerationPresetRequest,
    TestImageRequest,
    TypedNodeMappingValidateRequest,
    WorkflowAnalyzeRequest,
    WorkflowTemplateUpsert,
)
from app.services.admin_ai_service import (
    admin_ai_config_dto,
    admin_ai_models,
    apply_ai_task,
    create_ai_task,
    get_ai_task,
    list_character_templates,
    run_ai_task,
    save_admin_ai_config,
    test_admin_ai,
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
from app.services.admin_auth_service import require_admin_auth
from app.services.character_service import (
    character_bundle,
    create_character,
    get_default_character,
    get_character,
    publish_character,
    update_character,
)
from app.services.comfyui_service import comfyui_health
from app.services.comfyui_resource_service import (
    comfy_object_info,
    comfy_queue,
    comfyui_diagnostics,
    get_cached_resource,
    list_cached_resources,
    refresh_comfy_resources,
)
from app.services.llm_config_service import llm_config_dto, save_llm_config
from app.services.llm_service import (
    generate_character_card_with_llm,
    generate_single_turn_decision,
    llm_health,
)
from app.services.image_task_service import create_image_task
from app.services.workflow_analysis_service import (
    analyze_workflow,
    diagnose_workflow,
    draft_node_mapping,
    parse_workflow,
    validate_typed_node_mapping,
)


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin_auth)])


def cached_object_info(session: Session) -> dict[str, Any]:
    items = get_cached_resource(session, "nodeObjectInfo").get("items") or {}
    return items if isinstance(items, dict) else {}


def cached_resources(session: Session) -> dict[str, Any]:
    items = list_cached_resources(session).get("resources") or {}
    return items if isinstance(items, dict) else {}


@router.get("/system/llm-health")
def llm_health_api(session: Session = Depends(get_session)):
    return api_success(llm_health(session))


@router.get("/system/comfyui-health")
def comfyui_health_api():
    return api_success(comfyui_health())


@router.get("/ai-config")
def get_admin_ai_config_api(session: Session = Depends(get_session)):
    return api_success(admin_ai_config_dto(session))


@router.put("/ai-config")
def update_admin_ai_config_api(payload: AdminAIConfigUpdate, session: Session = Depends(get_session)):
    return api_success(save_admin_ai_config(session, payload))


@router.get("/ai-config/models")
def list_admin_ai_models_api(session: Session = Depends(get_session)):
    return api_success(admin_ai_models(session))


@router.post("/ai-config/test")
def test_admin_ai_config_api(payload: LLMConfigTestRequest, session: Session = Depends(get_session)):
    return api_success(test_admin_ai(session, payload.message))


@router.post("/ai-tasks")
def create_ai_task_api(
    payload: AITaskCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    task = create_ai_task(session, payload)
    background_tasks.add_task(run_ai_task, task.id)
    return api_success(task)


@router.get("/ai-tasks/{task_id}")
def get_ai_task_api(task_id: str, session: Session = Depends(get_session)):
    return api_success(get_ai_task(session, task_id))


@router.post("/ai-tasks/{task_id}/apply")
def apply_ai_task_api(task_id: str, payload: AITaskApplyRequest, session: Session = Depends(get_session)):
    return api_success(apply_ai_task(session, task_id, overwrite=payload.overwrite))


@router.get("/character-templates")
def list_character_templates_api(session: Session = Depends(get_session)):
    return api_success(list_character_templates(session))


@router.get("/comfyui/diagnostics")
def comfyui_diagnostics_api(session: Session = Depends(get_session)):
    return api_success(comfyui_diagnostics(session))


@router.post("/comfyui/resources/refresh")
def refresh_comfy_resources_api(
    _: ComfyResourceRefreshRequest | None = None,
    session: Session = Depends(get_session),
):
    return api_success(refresh_comfy_resources(session))


@router.get("/comfyui/resources")
def list_comfy_resources_api(session: Session = Depends(get_session)):
    return api_success(list_cached_resources(session))


@router.get("/comfyui/resources/{resource_type}")
def get_comfy_resource_api(resource_type: str, session: Session = Depends(get_session)):
    return api_success(get_cached_resource(session, resource_type))


@router.get("/comfyui/object-info")
def get_comfy_object_info_api(session: Session = Depends(get_session)):
    return api_success(comfy_object_info(session))


@router.get("/comfyui/queue")
def get_comfy_queue_api(session: Session = Depends(get_session)):
    return api_success(comfy_queue(session))


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


@router.post("/workflow-templates/parse")
def parse_workflow_template_api(payload: WorkflowAnalyzeRequest, session: Session = Depends(get_session)):
    parsed = parse_workflow(payload.workflowJson, object_info=cached_object_info(session), resources=cached_resources(session))
    mapping = draft_node_mapping(parsed)
    return api_success({**parsed, "guessedMapping": mapping, "typedMapping": mapping, "diagnosis": diagnose_workflow(parsed)})


@router.post("/workflow-templates/analyze-ai")
def analyze_workflow_template_ai_api(
    payload: WorkflowAnalyzeRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    task = create_ai_task(
        session,
        AITaskCreate(
            type="workflow.analyze",
            targetType="workflow",
            inputSnapshot={
                "workflowJson": payload.workflowJson,
                "objectInfo": cached_object_info(session),
                "resources": cached_resources(session),
            },
        ),
    )
    background_tasks.add_task(run_ai_task, task.id)
    return api_success(task)


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


@router.post("/workflow-templates/{workflow_id}/mapping-draft")
def workflow_mapping_draft_api(workflow_id: str, session: Session = Depends(get_session)):
    workflow = session.get(WorkflowTemplate, workflow_id)
    if not workflow:
        raise ApiError("WORKFLOW_TEMPLATE_NOT_FOUND", "Workflow template not found", 404)
    parsed = parse_workflow(workflow.workflow_json, object_info=cached_object_info(session), resources=cached_resources(session))
    return api_success({"analysis": parsed, "nodeMapping": draft_node_mapping(parsed), "diagnosis": diagnose_workflow(parsed)})


@router.post("/workflow-templates/{workflow_id}/diagnose")
def workflow_diagnose_api(workflow_id: str, session: Session = Depends(get_session)):
    workflow = session.get(WorkflowTemplate, workflow_id)
    if not workflow:
        raise ApiError("WORKFLOW_TEMPLATE_NOT_FOUND", "Workflow template not found", 404)
    parsed = parse_workflow(workflow.workflow_json, object_info=cached_object_info(session), resources=cached_resources(session))
    return api_success({"analysis": parsed, "diagnosis": diagnose_workflow(parsed), "nodeMapping": draft_node_mapping(parsed)})


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


@router.post("/node-mappings/{mapping_id}/validate-typed")
def validate_typed_node_mapping_api(
    mapping_id: str,
    payload: TypedNodeMappingValidateRequest | None = Body(default=None),
    session: Session = Depends(get_session),
):
    mapping = session.get(NodeMapping, mapping_id)
    if not mapping:
        raise ApiError("NODE_MAPPING_NOT_FOUND", "Node mapping not found", 404)
    workflow_json = payload.workflowJson if payload and payload.workflowJson else None
    if not workflow_json and payload and payload.workflowTemplateId:
        workflow = session.get(WorkflowTemplate, payload.workflowTemplateId)
        workflow_json = workflow.workflow_json if workflow else None
    if not workflow_json:
        workflow = session.exec(select(WorkflowTemplate).where(WorkflowTemplate.node_mapping_id == mapping_id)).first()
        workflow_json = workflow.workflow_json if workflow else None
    if not workflow_json:
        raise ApiError("WORKFLOW_TEMPLATE_REQUIRED", "workflowJson or bound WorkflowTemplate is required", 400)
    return api_success(
        validate_typed_node_mapping(
            workflow_json,
            payload.mappings if payload and payload.mappings else mapping.mappings,
            object_info=cached_object_info(session),
            resources=cached_resources(session),
        )
    )
