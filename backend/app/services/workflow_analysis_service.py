from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


CONNECTION_TYPES = {"MODEL", "CLIP", "VAE", "LATENT", "CONDITIONING", "IMAGE", "MASK"}
NUMERIC_FIELDS = {
    "seed": "INT",
    "steps": "INT",
    "width": "INT",
    "height": "INT",
    "batch_size": "INT",
    "cfg": "FLOAT",
    "denoise": "FLOAT",
    "strength_model": "FLOAT",
    "strength_clip": "FLOAT",
}
RESOURCE_FIELDS = {
    "ckpt_name": ("MODEL", "checkpoints"),
    "checkpoint": ("MODEL", "checkpoints"),
    "lora_name": ("MODEL", "loras"),
    "vae_name": ("VAE", "vae"),
}


def _class_type(node: dict[str, Any]) -> str:
    return str(node.get("class_type") or node.get("classType") or "")


def workflow_nodes(workflow_json: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(workflow_json, dict):
        return []
    nodes: list[dict[str, Any]] = []
    for node_id, node in workflow_json.items():
        if not isinstance(node, dict):
            continue
        nodes.append(
            {
                "nodeId": str(node_id),
                "classType": _class_type(node),
                "title": (node.get("_meta") or {}).get("title"),
                "inputs": node.get("inputs") or {},
            }
        )
    return nodes


def _has_input(node: dict[str, Any], key: str) -> bool:
    return isinstance(node.get("inputs"), dict) and key in node["inputs"]


def _is_connection(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and isinstance(value[1], int)
    )


def _schema_inputs(class_type: str, object_info: dict[str, Any] | None) -> dict[str, Any]:
    if not object_info:
        return {}
    node_schema = object_info.get(class_type) or {}
    raw_inputs = node_schema.get("input") or {}
    merged: dict[str, Any] = {}
    for bucket in ["required", "optional", "hidden"]:
        section = raw_inputs.get(bucket) or {}
        if isinstance(section, dict):
            merged.update(section)
    return merged


def _schema_value_type(schema_value: Any) -> tuple[str | None, dict[str, Any]]:
    meta: dict[str, Any] = {}
    if not isinstance(schema_value, list) or not schema_value:
        return None, meta
    first = schema_value[0]
    options = schema_value[1] if len(schema_value) > 1 and isinstance(schema_value[1], dict) else {}
    if isinstance(first, list):
        meta["options"] = [str(item) for item in first]
        return "ENUM", meta
    if isinstance(first, str):
        upper = first.upper()
        if upper in CONNECTION_TYPES:
            return upper, meta
        if upper in {"STRING", "INT", "FLOAT", "BOOLEAN"}:
            meta.update({key: options.get(key) for key in ["default", "min", "max", "step"] if key in options})
            return upper, meta
    return None, meta


def _infer_type(input_name: str, value: Any, schema_value: Any = None) -> tuple[str, dict[str, Any]]:
    schema_type, schema_meta = _schema_value_type(schema_value)
    if schema_type:
        return schema_type, schema_meta
    if _is_connection(value):
        return "UNKNOWN", {"connection": True}
    if input_name in NUMERIC_FIELDS:
        return NUMERIC_FIELDS[input_name], {}
    if input_name in RESOURCE_FIELDS:
        value_type, resource_type = RESOURCE_FIELDS[input_name]
        return value_type, {"resourceType": resource_type}
    if input_name in {"sampler_name", "scheduler"}:
        return "ENUM", {}
    if isinstance(value, bool):
        return "BOOLEAN", {}
    if isinstance(value, int) and not isinstance(value, bool):
        return "INT", {}
    if isinstance(value, float):
        return "FLOAT", {}
    if isinstance(value, str):
        return "STRING", {}
    return "UNKNOWN", {}


def _widget_type(value_type: str, input_name: str, meta: dict[str, Any]) -> str:
    if value_type == "BOOLEAN":
        return "switch"
    if value_type in {"INT", "FLOAT"}:
        return "number"
    if value_type == "ENUM" or meta.get("resourceType"):
        return "select"
    if input_name in {"text", "prompt", "negative_prompt"}:
        return "textarea"
    if value_type in CONNECTION_TYPES:
        return "connection"
    return "text"


def _resource_exists(value: Any, resource_type: str, resources: dict[str, Any]) -> bool | None:
    if not value:
        return None
    bucket = resources.get(resource_type)
    if isinstance(bucket, dict):
        items = bucket.get("items", [])
    else:
        items = bucket or []
    if not items:
        return None
    normalized = {str(item if not isinstance(item, dict) else item.get("name") or item.get("id") or item) for item in items}
    return str(value) in normalized


def _input_item(
    node_id: str,
    class_type: str,
    input_name: str,
    value: Any,
    object_info: dict[str, Any] | None,
    resources: dict[str, Any] | None,
) -> dict[str, Any]:
    schema_inputs = _schema_inputs(class_type, object_info)
    value_type, meta = _infer_type(input_name, value, schema_inputs.get(input_name))
    is_connection = _is_connection(value)
    item = {
        "name": input_name,
        "inputPath": f"inputs.{input_name}",
        "value": value,
        "isConnection": is_connection,
        "valueType": value_type,
        "widgetType": _widget_type(value_type, input_name, meta),
    }
    if is_connection:
        item["connectedNodeId"] = str(value[0])
        item["connectedOutputIndex"] = value[1]
        item["widgetType"] = "connection"
    if "options" in meta:
        item["options"] = meta["options"]
    for key in ["default", "min", "max", "step", "resourceType"]:
        if key in meta and meta[key] is not None:
            item[key] = meta[key]
    if input_name in {"sampler_name", "scheduler"}:
        item["resourceType"] = "samplers" if input_name == "sampler_name" else "schedulers"
    if item.get("resourceType") and resources:
        exists = _resource_exists(value, item["resourceType"], resources)
        if exists is not None:
            item["resourceExists"] = exists
    return item


def parse_workflow(
    workflow_json: dict[str, Any],
    *,
    object_info: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes = []
    edges = []
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)

    for node_id, node in (workflow_json or {}).items():
        if not isinstance(node, dict):
            continue
        node_id_text = str(node_id)
        class_type = _class_type(node)
        raw_inputs = node.get("inputs") or {}
        inputs = []
        for name, value in raw_inputs.items():
            item = _input_item(node_id_text, class_type, str(name), value, object_info, resources)
            inputs.append(item)
            if item["isConnection"]:
                source = item["connectedNodeId"]
                outgoing[source].append(node_id_text)
                incoming[node_id_text].append(source)
                edges.append(
                    {
                        "fromNodeId": source,
                        "fromOutputIndex": item["connectedOutputIndex"],
                        "toNodeId": node_id_text,
                        "toInput": name,
                    }
                )
        nodes.append(
            {
                "nodeId": node_id_text,
                "classType": class_type,
                "class_type": class_type,
                "title": (node.get("_meta") or {}).get("title"),
                "inputs": inputs,
                "rawInputs": raw_inputs,
                "inputNames": list(raw_inputs.keys()),
                "incomingNodeIds": incoming.get(node_id_text, []),
                "outgoingNodeIds": outgoing.get(node_id_text, []),
                "knownByObjectInfo": bool(object_info and class_type in object_info),
            }
        )

    node_map = {node["nodeId"]: node for node in nodes}
    for node in nodes:
        node["outgoingNodeIds"] = sorted(set(outgoing.get(node["nodeId"], [])))
        node["incomingNodeIds"] = sorted(set(incoming.get(node["nodeId"], [])))

    output_nodes = [
        node
        for node in nodes
        if "saveimage" in node["classType"].lower()
        or "previewimage" in node["classType"].lower()
        or any(item["name"] == "images" for item in node["inputs"])
    ]
    loader_nodes = [node for node in nodes if "checkpoint" in node["classType"].lower() or "loader" in node["classType"].lower()]
    sampler_nodes = [node for node in nodes if "sampler" in node["classType"].lower()]
    prompt_nodes = [node for node in nodes if "cliptextencode" in node["classType"].lower() or any(item["name"] == "text" for item in node["inputs"])]

    return {
        "analyzedNodes": len(nodes),
        "nodes": nodes,
        "edges": edges,
        "dag": {
            "nodeIds": list(node_map.keys()),
            "edges": edges,
            "outputNodeIds": [node["nodeId"] for node in output_nodes],
        },
        "nodeClasses": sorted({node["classType"] for node in nodes if node["classType"]}),
        "summary": {
            "loaderNodeIds": [node["nodeId"] for node in loader_nodes],
            "promptNodeIds": [node["nodeId"] for node in prompt_nodes],
            "samplerNodeIds": [node["nodeId"] for node in sampler_nodes],
            "outputNodeIds": [node["nodeId"] for node in output_nodes],
        },
    }


def _input_by_name(node: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((item for item in node.get("inputs", []) if item.get("name") == name), None)


def _mapping_spec(node: dict[str, Any], input_item: dict[str, Any], *, key: str, confidence: float, reason: str) -> dict[str, Any]:
    spec = {
        "nodeId": node["nodeId"],
        "inputPath": input_item["inputPath"],
        "valueType": input_item["valueType"],
        "widgetType": input_item["widgetType"],
        "confidence": confidence,
        "reason": reason,
    }
    for name in ["min", "max", "step", "options", "resourceType"]:
        if name in input_item:
            spec[name] = input_item[name]
    if input_item.get("name") == "sampler_name":
        spec["optionsSource"] = f"objectInfo.{node['classType']}.inputs.sampler_name"
    if input_item.get("name") == "scheduler":
        spec["optionsSource"] = f"objectInfo.{node['classType']}.inputs.scheduler"
    return spec


def draft_node_mapping(parsed: dict[str, Any]) -> dict[str, Any]:
    nodes = parsed.get("nodes", [])
    mapping: dict[str, Any] = {}

    text_nodes = [node for node in nodes if _input_by_name(node, "text")]
    negative_node = None
    for node in text_nodes:
        text_item = _input_by_name(node, "text")
        value = str((text_item or {}).get("value") or "").lower()
        title = str(node.get("title") or "").lower()
        if any(word in value or word in title for word in ["negative", "low quality", "bad", "blurry", "反向"]):
            negative_node = node
            break
    positive_node = next((node for node in text_nodes if node is not negative_node), text_nodes[0] if text_nodes else None)
    if not negative_node and len(text_nodes) > 1:
        negative_node = text_nodes[1]

    if positive_node and (item := _input_by_name(positive_node, "text")) and not item["isConnection"]:
        mapping["positivePrompt"] = _mapping_spec(positive_node, item, key="positivePrompt", confidence=0.95, reason="CLIPTextEncode 的 text 输入通常承载正向提示词")
    if negative_node and (item := _input_by_name(negative_node, "text")) and not item["isConnection"]:
        mapping["negativePrompt"] = _mapping_spec(negative_node, item, key="negativePrompt", confidence=0.9, reason="该文本节点包含 negative/低质量 等反向提示特征")

    for node in nodes:
        class_name = node.get("classType", "").lower()
        if "checkpoint" in class_name or _input_by_name(node, "ckpt_name"):
            item = _input_by_name(node, "ckpt_name") or _input_by_name(node, "checkpoint")
            if item and not item["isConnection"]:
                mapping["checkpoint"] = _mapping_spec(node, item, key="checkpoint", confidence=0.95, reason="CheckpointLoader 节点的模型名称输入")
        if "emptylatentimage" in class_name or (_input_by_name(node, "width") and _input_by_name(node, "height")):
            for key in ["width", "height"]:
                item = _input_by_name(node, key)
                if item and not item["isConnection"]:
                    mapping[key] = _mapping_spec(node, item, key=key, confidence=0.95, reason="空 Latent 节点控制生成尺寸")
        if "sampler" in class_name or (_input_by_name(node, "steps") and _input_by_name(node, "cfg")):
            for key, input_name in {
                "seed": "seed",
                "steps": "steps",
                "cfg": "cfg",
                "sampler": "sampler_name",
                "scheduler": "scheduler",
            }.items():
                item = _input_by_name(node, input_name)
                if item and not item["isConnection"]:
                    mapping[key] = _mapping_spec(node, item, key=key, confidence=0.95, reason="KSampler 采样参数输入")
        if "lora" in class_name and _input_by_name(node, "lora_name"):
            item_name = _input_by_name(node, "lora_name")
            model = _input_by_name(node, "strength_model")
            clip = _input_by_name(node, "strength_clip")
            if item_name and model and clip:
                mapping.setdefault("loras", []).append(
                    {
                        "nodeId": node["nodeId"],
                        "nameInputPath": item_name["inputPath"],
                        "strengthModelInputPath": model["inputPath"],
                        "strengthClipInputPath": clip["inputPath"],
                        "valueType": "MODEL",
                        "widgetType": "lora-table",
                        "confidence": 0.9,
                        "reason": "LoRA 节点包含名称和模型/CLIP 强度输入",
                    }
                )
    return mapping


def guess_node_mapping(workflow_json: dict[str, Any]) -> dict[str, Any]:
    return draft_node_mapping(parse_workflow(workflow_json))


def _reachable_to_output(parsed: dict[str, Any]) -> bool:
    output_ids = set(parsed.get("dag", {}).get("outputNodeIds") or [])
    if not output_ids:
        return False
    edges = parsed.get("edges", [])
    reverse: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        reverse[edge["toNodeId"]].append(edge["fromNodeId"])
    seen = set()
    queue = deque(output_ids)
    while queue:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        for source in reverse.get(node_id, []):
            queue.append(source)
    return len(seen) > len(output_ids)


def diagnose_workflow(parsed: dict[str, Any]) -> dict[str, Any]:
    classes = {str(name).lower() for name in parsed.get("nodeClasses", [])}
    summary = parsed.get("summary", {})
    warnings: list[str] = []
    if not summary.get("promptNodeIds"):
        warnings.append("没有识别到提示词编码节点，可能不是 text-to-image 工作流。")
    if not summary.get("samplerNodeIds"):
        warnings.append("没有识别到采样节点，无法确认生图主链路。")
    if not summary.get("outputNodeIds"):
        warnings.append("没有识别到 SaveImage 或图片输出节点。")
    if not _reachable_to_output(parsed):
        warnings.append("输出节点没有形成可达的上游链路，请检查节点连接。")
    workflow_type = "text-to-image"
    if any("loadimage" in item for item in classes):
        workflow_type = "image-to-image"
    if any("inpaint" in item for item in classes) or any("mask" in item for item in classes):
        workflow_type = "inpaint"
    if any("controlnet" in item for item in classes):
        workflow_type = "controlnet"
    if not summary.get("promptNodeIds") or not summary.get("samplerNodeIds"):
        workflow_type = "unknown"

    return {
        "workflowType": workflow_type,
        "supportedForMvp": workflow_type == "text-to-image",
        "summary": "该工作流看起来是 text-to-image 生图链路。" if workflow_type == "text-to-image" else "该工作流不是标准 MVP text-to-image，建议只做诊断不直接上线。",
        "keyPath": {
            "loader": summary.get("loaderNodeIds", []),
            "promptEncode": summary.get("promptNodeIds", []),
            "sampler": summary.get("samplerNodeIds", []),
            "output": summary.get("outputNodeIds", []),
        },
        "mustKeepNodeIds": sorted(set(summary.get("loaderNodeIds", []) + summary.get("promptNodeIds", []) + summary.get("samplerNodeIds", []) + summary.get("outputNodeIds", []))),
        "injectableNodeIds": sorted({spec["nodeId"] for spec in draft_node_mapping(parsed).values() if isinstance(spec, dict)}),
        "warnings": warnings,
        "suggestions": ["先校验 NodeMapping，再保存 Workflow。", "checkpoint、LoRA、VAE 请从 ComfyUI 资源中心下拉选择，避免手输名称错误。"],
    }


def input_path_exists(node: dict[str, Any], input_path: str) -> bool:
    current: Any = node
    for part in [item for item in input_path.split(".") if item]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _input_from_path(parsed: dict[str, Any], node_id: str, input_path: str) -> dict[str, Any] | None:
    input_name = input_path.split(".")[-1]
    node = next((item for item in parsed.get("nodes", []) if item["nodeId"] == str(node_id)), None)
    if not node:
        return None
    return _input_by_name(node, input_name)


def validate_typed_node_mapping(
    workflow_json: dict[str, Any],
    mapping: dict[str, Any],
    *,
    object_info: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = parse_workflow(workflow_json, object_info=object_info, resources=resources)
    workflow = workflow_json or {}
    node_ids = {str(node_id) for node_id in workflow.keys()}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not isinstance(mapping, dict):
        errors.append({"code": "NODE_MAPPING_INVALID", "message": "NodeMapping 必须是 JSON 对象。"})
        return {"valid": False, "errors": errors, "warnings": warnings, "analysis": parsed}
    if not isinstance(mapping.get("positivePrompt"), dict):
        errors.append({"code": "NODE_MAPPING_REQUIRED", "message": "positivePrompt 映射是必需项。"})

    for key, spec in mapping.items():
        specs: list[tuple[str, dict[str, Any]]] = []
        if key == "loras" and isinstance(spec, list):
            for index, item in enumerate(spec):
                if isinstance(item, dict):
                    for path_key in ["nameInputPath", "strengthModelInputPath", "strengthClipInputPath"]:
                        specs.append((f"loras[{index}].{path_key}", {"nodeId": item.get("nodeId"), "inputPath": item.get(path_key)}))
            continue
        if isinstance(spec, dict):
            specs.append((key, spec))
        for label, item in specs:
            node_id = str(item.get("nodeId") or "")
            input_path = str(item.get("inputPath") or "")
            if not node_id or node_id not in node_ids:
                errors.append({"code": "NODE_MAPPING_NODE_MISSING", "message": f"{label} 的 nodeId 不存在。", "nodeId": node_id})
                continue
            node = workflow.get(node_id) or {}
            if not input_path or not input_path_exists(node, input_path):
                errors.append({"code": "NODE_MAPPING_INPUT_INVALID", "message": f"{label} 的 inputPath 不存在。", "nodeId": node_id, "inputPath": input_path})
                continue
            input_item = _input_from_path(parsed, node_id, input_path)
            if input_item and input_item.get("isConnection"):
                errors.append({"code": "NODE_MAPPING_CONNECTION_INPUT", "message": f"{label} 指向连接输入，不能作为普通值覆盖。", "nodeId": node_id, "inputPath": input_path})
            expected = item.get("valueType")
            actual = input_item.get("valueType") if input_item else None
            if expected and actual and expected != actual and actual != "UNKNOWN":
                warnings.append({"code": "NODE_MAPPING_TYPE_MISMATCH", "message": f"{label} 声明类型 {expected}，实际解析为 {actual}。", "nodeId": node_id})
            if input_item and input_item.get("resourceType") and input_item.get("resourceExists") is False:
                errors.append({"code": "NODE_MAPPING_RESOURCE_MISSING", "message": f"{label} 使用的资源在 ComfyUI 缓存中不存在。", "resourceType": input_item["resourceType"], "value": input_item.get("value")})

    diagnosis = diagnose_workflow(parsed)
    if not diagnosis["supportedForMvp"]:
        errors.append({"code": "WORKFLOW_TYPE_UNSUPPORTED", "message": "当前 MVP 仅完整支持 text-to-image 工作流。", "workflowType": diagnosis["workflowType"]})
    if not parsed.get("summary", {}).get("outputNodeIds"):
        errors.append({"code": "WORKFLOW_OUTPUT_MISSING", "message": "没有发现 SaveImage 或等价图片输出节点。"})
    missing_custom_nodes = [node for node in parsed.get("nodes", []) if object_info and not node.get("knownByObjectInfo")]
    for node in missing_custom_nodes:
        warnings.append({"code": "WORKFLOW_CUSTOM_NODE_UNKNOWN", "message": f"节点 {node['nodeId']} / {node['classType']} 不在 object_info 中，可能缺少自定义节点。"})

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "analysis": parsed,
        "diagnosis": diagnosis,
        "fixSuggestions": diagnosis.get("suggestions", []),
    }


def analyze_workflow(workflow_json: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_workflow(workflow_json)
    mapping = draft_node_mapping(parsed)
    return {
        **parsed,
        "guessedMapping": mapping,
        "typedMapping": mapping,
        "diagnosis": diagnose_workflow(parsed),
    }
