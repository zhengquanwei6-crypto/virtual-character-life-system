from __future__ import annotations

from typing import Any


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
                "classType": node.get("class_type") or node.get("classType") or "",
                "inputs": node.get("inputs") or {},
            }
        )
    return nodes


def _has_input(node: dict[str, Any], key: str) -> bool:
    return isinstance(node.get("inputs"), dict) and key in node["inputs"]


def guess_node_mapping(workflow_json: dict[str, Any]) -> dict[str, Any]:
    nodes = workflow_nodes(workflow_json)
    mapping: dict[str, Any] = {}
    text_nodes = [
        node
        for node in nodes
        if "cliptextencode" in node["classType"].lower() or _has_input(node, "text")
    ]
    negative_words = ["negative", "low quality", "bad", "blurry", "worst", "deformed", "反向"]
    negative_node = next(
        (
            node
            for node in text_nodes
            if any(word in str(node["inputs"].get("text", "")).lower() for word in negative_words)
        ),
        text_nodes[1] if len(text_nodes) > 1 else None,
    )
    positive_node = next((node for node in text_nodes if node is not negative_node), text_nodes[0] if text_nodes else None)

    if positive_node:
        mapping["positivePrompt"] = {"nodeId": positive_node["nodeId"], "inputPath": "inputs.text"}
    if negative_node:
        mapping["negativePrompt"] = {"nodeId": negative_node["nodeId"], "inputPath": "inputs.text"}

    checkpoint_node = next(
        (
            node
            for node in nodes
            if "checkpoint" in node["classType"].lower() or _has_input(node, "ckpt_name")
        ),
        None,
    )
    if checkpoint_node:
        mapping["checkpoint"] = {"nodeId": checkpoint_node["nodeId"], "inputPath": "inputs.ckpt_name"}

    latent_node = next(
        (
            node
            for node in nodes
            if "emptylatentimage" in node["classType"].lower() or (_has_input(node, "width") and _has_input(node, "height"))
        ),
        None,
    )
    if latent_node:
        mapping["width"] = {"nodeId": latent_node["nodeId"], "inputPath": "inputs.width"}
        mapping["height"] = {"nodeId": latent_node["nodeId"], "inputPath": "inputs.height"}

    sampler_node = next(
        (
            node
            for node in nodes
            if "ksampler" in node["classType"].lower()
            or (_has_input(node, "seed") and _has_input(node, "steps") and _has_input(node, "cfg"))
        ),
        None,
    )
    if sampler_node:
        paths = {
            "seed": "inputs.seed",
            "steps": "inputs.steps",
            "cfg": "inputs.cfg",
            "sampler": "inputs.sampler_name",
            "scheduler": "inputs.scheduler",
        }
        for key, path in paths.items():
            input_name = path.split(".")[-1]
            if _has_input(sampler_node, input_name):
                mapping[key] = {"nodeId": sampler_node["nodeId"], "inputPath": path}

    return mapping


def analyze_workflow(workflow_json: dict[str, Any]) -> dict[str, Any]:
    nodes = workflow_nodes(workflow_json)
    return {
        "analyzedNodes": len(nodes),
        "nodes": nodes,
        "guessedMapping": guess_node_mapping(workflow_json),
    }
