from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import (
    Character,
    CharacterProfile,
    CharacterPrompt,
    CharacterVisual,
    GenerationPreset,
    NodeMapping,
    WorkflowTemplate,
    utc_now,
)


def seed_database(session: Session) -> None:
    existing = session.exec(select(Character).where(Character.is_default == True)).first()  # noqa: E712
    if existing:
        return

    mapping = NodeMapping(
        name="Default text-to-image mapping",
        description="Mock mapping for the MVP text-to-image workflow.",
        status="active",
        version=1,
        mappings={
            "positivePrompt": {"nodeId": "6", "inputPath": "inputs.text"},
            "negativePrompt": {"nodeId": "7", "inputPath": "inputs.text"},
            "checkpoint": {"nodeId": "4", "inputPath": "inputs.ckpt_name"},
            "width": {"nodeId": "5", "inputPath": "inputs.width"},
            "height": {"nodeId": "5", "inputPath": "inputs.height"},
            "steps": {"nodeId": "3", "inputPath": "inputs.steps"},
            "cfg": {"nodeId": "3", "inputPath": "inputs.cfg"},
            "sampler": {"nodeId": "3", "inputPath": "inputs.sampler_name"},
            "scheduler": {"nodeId": "3", "inputPath": "inputs.scheduler"},
            "seed": {"nodeId": "3", "inputPath": "inputs.seed"},
        },
    )
    session.add(mapping)
    session.commit()
    session.refresh(mapping)

    workflow = WorkflowTemplate(
        name="Default ComfyUI text-to-image workflow",
        description="Mock workflow template for text-to-image.",
        status="active",
        version=1,
        node_mapping_id=mapping.id,
        workflow_json={
            "3": {"class_type": "KSampler", "inputs": {}},
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {}},
        },
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)

    preset = GenerationPreset(
        name="Default portrait preset",
        description="Default mock generation preset.",
        status="active",
        version=1,
        workflow_template_id=workflow.id,
        checkpoint="mock_model.safetensors",
        loras=[],
        width=768,
        height=1024,
        steps=24,
        cfg=7.0,
        sampler="euler",
        scheduler="normal",
        seed_mode="random",
        positive_prompt_prefix="masterpiece, best quality",
        positive_prompt_suffix="soft light, detailed face",
        negative_prompt="low quality, blurry, bad anatomy",
        activated_at=datetime.now(timezone.utc),
    )
    session.add(preset)
    session.commit()
    session.refresh(preset)

    character = Character(
        code="default_character",
        status="active",
        version=1,
        is_default=True,
        published_at=datetime.now(timezone.utc),
    )
    session.add(character)
    session.commit()
    session.refresh(character)

    profile = CharacterProfile(
        character_id=character.id,
        name="Mira",
        avatar_url="https://placehold.co/256x256.png?text=Mira",
        description="A warm virtual companion for the MVP chat experience.",
        personality="curious, gentle, expressive",
        scenario="Mira chats with the user and can imagine scenes as pictures.",
        first_message="Hello, I am Mira. What would you like to talk about today?",
        tags=["default", "mvp"],
    )
    prompt = CharacterPrompt(
        character_id=character.id,
        system_prompt="You are Mira, a friendly virtual character.",
        roleplay_prompt="Stay in character and respond warmly.",
        conversation_style="concise, vivid, emotionally aware",
        safety_prompt="Avoid unsafe or harmful content.",
    )
    visual = CharacterVisual(
        character_id=character.id,
        visual_prompt="Mira, virtual anime girl, silver hair, blue eyes",
        visual_negative_prompt="extra fingers, distorted face",
        generation_preset_id=preset.id,
    )
    session.add(profile)
    session.add(prompt)
    session.add(visual)
    session.commit()
    session.refresh(profile)
    session.refresh(prompt)
    session.refresh(visual)

    character.profile_id = profile.id
    character.prompt_id = prompt.id
    character.visual_id = visual.id
    character.updated_at = utc_now()
    session.add(character)
    session.commit()
