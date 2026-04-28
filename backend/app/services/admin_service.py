from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models import GenerationPreset, NodeMapping, WorkflowTemplate, utc_now
from app.responses import ApiError
from app.schemas import GenerationPresetUpsert, NodeMappingUpsert, WorkflowTemplateUpsert
from app.services.comfyui_service import normalize_comfy_workflow_json


def create_generation_preset(session: Session, payload: GenerationPresetUpsert) -> GenerationPreset:
    preset = GenerationPreset(
        name=payload.name,
        description=payload.description,
        workflow_template_id=payload.workflowTemplateId,
        checkpoint=payload.checkpoint,
        loras=payload.loras,
        width=payload.width,
        height=payload.height,
        steps=payload.steps,
        cfg=payload.cfg,
        sampler=payload.sampler,
        scheduler=payload.scheduler,
        seed_mode=payload.seedMode,
        seed=payload.seed,
        positive_prompt_prefix=payload.positivePromptPrefix,
        positive_prompt_suffix=payload.positivePromptSuffix,
        negative_prompt=payload.negativePrompt,
    )
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def update_generation_preset(session: Session, preset_id: str, payload: GenerationPresetUpsert) -> GenerationPreset:
    preset = session.get(GenerationPreset, preset_id)
    if not preset:
        raise ApiError("GENERATION_PRESET_NOT_FOUND", "Generation preset not found", 404)
    preset.name = payload.name
    preset.description = payload.description
    preset.workflow_template_id = payload.workflowTemplateId
    preset.checkpoint = payload.checkpoint
    preset.loras = payload.loras
    preset.width = payload.width
    preset.height = payload.height
    preset.steps = payload.steps
    preset.cfg = payload.cfg
    preset.sampler = payload.sampler
    preset.scheduler = payload.scheduler
    preset.seed_mode = payload.seedMode
    preset.seed = payload.seed
    preset.positive_prompt_prefix = payload.positivePromptPrefix
    preset.positive_prompt_suffix = payload.positivePromptSuffix
    preset.negative_prompt = payload.negativePrompt
    preset.version += 1
    preset.updated_at = utc_now()
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def activate_generation_preset(session: Session, preset_id: str) -> GenerationPreset:
    preset = session.get(GenerationPreset, preset_id)
    if not preset:
        raise ApiError("GENERATION_PRESET_NOT_FOUND", "Generation preset not found", 404)
    workflow = session.get(WorkflowTemplate, preset.workflow_template_id)
    if not workflow:
        raise ApiError("WORKFLOW_TEMPLATE_NOT_FOUND", "Workflow template not found", 404)
    validation = validate_workflow_template(session, workflow.id)
    if not validation["valid"]:
        raise ApiError("ACTIVATE_FAILED", "Generation preset cannot be activated", 400, validation)
    preset.status = "active"
    preset.version += 1
    preset.activated_at = utc_now()
    preset.updated_at = utc_now()
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def create_workflow_template(session: Session, payload: WorkflowTemplateUpsert) -> WorkflowTemplate:
    workflow = WorkflowTemplate(
        name=payload.name,
        description=payload.description,
        workflow_json=normalize_comfy_workflow_json(payload.workflowJson),
        node_mapping_id=payload.nodeMappingId,
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


def update_workflow_template(session: Session, workflow_id: str, payload: WorkflowTemplateUpsert) -> WorkflowTemplate:
    workflow = session.get(WorkflowTemplate, workflow_id)
    if not workflow:
        raise ApiError("WORKFLOW_TEMPLATE_NOT_FOUND", "Workflow template not found", 404)
    workflow.name = payload.name
    workflow.description = payload.description
    workflow.workflow_json = normalize_comfy_workflow_json(payload.workflowJson)
    workflow.node_mapping_id = payload.nodeMappingId
    workflow.version += 1
    workflow.updated_at = utc_now()
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


def validate_workflow_template(session: Session, workflow_id: str) -> dict:
    workflow = session.get(WorkflowTemplate, workflow_id)
    if not workflow:
        raise ApiError("WORKFLOW_TEMPLATE_NOT_FOUND", "Workflow template not found", 404)
    errors = []
    if not isinstance(workflow.workflow_json, dict) or not workflow.workflow_json:
        errors.append({"code": "WORKFLOW_TEMPLATE_INVALID", "message": "workflowJson must be a non-empty object"})
    if not workflow.node_mapping_id:
        errors.append({"code": "WORKFLOW_MAPPING_REQUIRED", "message": "nodeMappingId is required"})
    elif not session.get(NodeMapping, workflow.node_mapping_id):
        errors.append({"code": "NODE_MAPPING_NOT_FOUND", "message": "Node mapping not found"})
    return {"valid": len(errors) == 0, "errors": errors}


def create_node_mapping(session: Session, payload: NodeMappingUpsert) -> NodeMapping:
    mapping = NodeMapping(name=payload.name, description=payload.description, mappings=payload.mappings)
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping


def update_node_mapping(session: Session, mapping_id: str, payload: NodeMappingUpsert) -> NodeMapping:
    mapping = session.get(NodeMapping, mapping_id)
    if not mapping:
        raise ApiError("NODE_MAPPING_NOT_FOUND", "Node mapping not found", 404)
    mapping.name = payload.name
    mapping.description = payload.description
    mapping.mappings = payload.mappings
    mapping.version += 1
    mapping.updated_at = utc_now()
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping


def input_path_exists(node: dict[str, Any], input_path: str) -> bool:
    current: Any = node
    for part in [item for item in input_path.split(".") if item]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def workflow_for_mapping(
    session: Session,
    mapping_id: str,
    workflow_json: dict[str, Any] | None = None,
    workflow_template_id: str | None = None,
) -> dict[str, Any] | None:
    if workflow_json:
        return workflow_json
    if workflow_template_id:
        workflow = session.get(WorkflowTemplate, workflow_template_id)
        return workflow.workflow_json if workflow else None
    workflow = session.exec(select(WorkflowTemplate).where(WorkflowTemplate.node_mapping_id == mapping_id)).first()
    return workflow.workflow_json if workflow else None


def validate_single_mapping(
    workflow_json: dict[str, Any],
    key: str,
    spec: dict[str, Any],
    missing_nodes: list[str],
    invalid_input_paths: list[str],
    errors: list[dict[str, Any]],
) -> None:
    node_id = str(spec.get("nodeId", ""))
    input_path = spec.get("inputPath")
    if not node_id or node_id not in workflow_json:
        missing_nodes.append(key)
        errors.append({"code": "NODE_MAPPING_NODE_MISSING", "message": f"{key}.nodeId is missing", "nodeId": node_id})
        return
    if not input_path or not input_path_exists(workflow_json[node_id], input_path):
        invalid_input_paths.append(key)
        errors.append(
            {
                "code": "NODE_MAPPING_INPUT_INVALID",
                "message": f"{key}.inputPath is invalid",
                "nodeId": node_id,
                "inputPath": input_path,
            }
        )


def validate_node_mapping(
    session: Session,
    mapping_id: str,
    workflow_json: dict[str, Any] | None = None,
    workflow_template_id: str | None = None,
) -> dict:
    mapping = session.get(NodeMapping, mapping_id)
    if not mapping:
        raise ApiError("NODE_MAPPING_NOT_FOUND", "Node mapping not found", 404)
    missing_nodes = []
    invalid_input_paths = []
    errors = []
    if not isinstance(mapping.mappings, dict):
        errors.append({"code": "NODE_MAPPING_INVALID", "message": "positivePrompt mapping is required"})
        return {
            "valid": False,
            "missingNodes": missing_nodes,
            "invalidInputPaths": invalid_input_paths,
            "errors": errors,
        }

    workflow = workflow_for_mapping(session, mapping_id, workflow_json, workflow_template_id)
    if not isinstance(workflow, dict) or not workflow:
        errors.append({"code": "WORKFLOW_TEMPLATE_REQUIRED", "message": "workflowJson or bound WorkflowTemplate is required"})
        return {
            "valid": False,
            "missingNodes": missing_nodes,
            "invalidInputPaths": invalid_input_paths,
            "errors": errors,
        }

    if not isinstance(mapping.mappings.get("positivePrompt"), dict):
        errors.append({"code": "NODE_MAPPING_INVALID", "message": "positivePrompt mapping is required"})

    for key, spec in mapping.mappings.items():
        if key == "loras":
            for index, lora_spec in enumerate(spec or []):
                node_id = str(lora_spec.get("nodeId", ""))
                if not node_id or node_id not in workflow:
                    missing_nodes.append(f"loras[{index}]")
                    errors.append({"code": "NODE_MAPPING_NODE_MISSING", "message": f"loras[{index}].nodeId is missing", "nodeId": node_id})
                    continue
                for path_key in ["nameInputPath", "strengthModelInputPath", "strengthClipInputPath"]:
                    input_path = lora_spec.get(path_key)
                    if not input_path or not input_path_exists(workflow[node_id], input_path):
                        invalid_input_paths.append(f"loras[{index}].{path_key}")
                        errors.append(
                            {
                                "code": "NODE_MAPPING_INPUT_INVALID",
                                "message": f"loras[{index}].{path_key} is invalid",
                                "nodeId": node_id,
                                "inputPath": input_path,
                            }
                        )
            continue
        if isinstance(spec, dict):
            validate_single_mapping(workflow, key, spec, missing_nodes, invalid_input_paths, errors)
    return {
        "valid": len(errors) == 0,
        "missingNodes": missing_nodes,
        "invalidInputPaths": invalid_input_paths,
        "errors": errors,
    }
