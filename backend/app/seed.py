from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import (
    Character,
    CharacterProfile,
    CharacterPrompt,
    CharacterTemplate,
    CharacterVisual,
    GenerationPreset,
    NodeMapping,
    WorkflowTemplate,
    utc_now,
)


def seed_character_templates(session: Session) -> None:
    existing = session.exec(select(CharacterTemplate)).first()
    if existing:
        return
    templates = [
        CharacterTemplate(
            name="温柔陪伴者",
            category="陪伴",
            description="适合日常聊天、情绪陪伴和轻量图文互动的默认角色方向。",
            profile_draft={
                "name": "Mira",
                "description": "温柔、稳定、会主动把对话变成画面的虚拟陪伴者。",
                "personality": "温柔、敏锐、可靠、有一点俏皮",
                "scenario": "陪用户聊天、整理想法，并在合适时生成画面。",
                "firstMessage": "你好，我在这里。今天想让我陪你聊点什么？",
                "tags": ["陪伴", "温柔", "生图"],
            },
            prompt_draft={
                "systemPrompt": "你是一个稳定、温柔、边界清晰的虚拟角色。",
                "roleplayPrompt": "保持角色一致性，用自然中文回应；用户想看画面时给出清晰画面描述。",
                "conversationStyle": "简洁、细腻、亲近但不过界",
                "safetyPrompt": "避免危险、违法或伤害性内容。",
            },
            visual_draft={
                "visualPrompt": "warm virtual companion, expressive eyes, clean outfit, soft light, high quality portrait",
                "visualNegativePrompt": "low quality, blurry, bad anatomy, watermark",
            },
            tags=["built-in", "companion"],
        ),
        CharacterTemplate(
            name="冷静创作助手",
            category="效率",
            description="适合帮助用户整理设定、优化提示词、生成创意方向。",
            profile_draft={
                "name": "Noa",
                "description": "冷静、专业、反应快的创作型虚拟助手。",
                "personality": "理性、清晰、耐心、善于拆解问题",
                "scenario": "协助用户规划角色、提示词、画面与项目迭代。",
                "firstMessage": "我准备好了。我们先把目标拆成几个可执行的小步骤吧。",
                "tags": ["效率", "创作", "提示词"],
            },
            prompt_draft={
                "systemPrompt": "你是一个专业的创作助手，回答必须清晰、可执行、少废话。",
                "roleplayPrompt": "优先给出结构化建议，并主动指出风险和下一步。",
                "conversationStyle": "简洁、准确、专业",
                "safetyPrompt": "避免提供不安全执行建议。",
            },
            visual_draft={
                "visualPrompt": "calm futuristic assistant, clean design, intelligent expression, studio lighting",
                "visualNegativePrompt": "messy background, low quality, distorted face",
            },
            tags=["built-in", "assistant"],
        ),
    ]
    for template in templates:
        session.add(template)
    session.commit()


def seed_database(session: Session) -> None:
    seed_character_templates(session)
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
        description="Default API-format ComfyUI text-to-image workflow.",
        status="active",
        version=1,
        node_mapping_id=mapping.id,
        workflow_json={
            "3": {
                "inputs": {
                    "seed": 639651158536171,
                    "steps": 20,
                    "cfg": 8,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
                "_meta": {"title": "KSampler"},
            },
            "4": {
                "inputs": {"ckpt_name": "Qwen-Rapid-AIO-NSFW-v11.safetensors"},
                "class_type": "CheckpointLoaderSimple",
                "_meta": {"title": "CheckpointLoaderSimple"},
            },
            "5": {
                "inputs": {"width": 512, "height": 512, "batch_size": 1},
                "class_type": "EmptyLatentImage",
                "_meta": {"title": "EmptyLatentImage"},
            },
            "6": {
                "inputs": {"text": "portrait, best quality", "clip": ["4", 1]},
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "PositivePrompt"},
            },
            "7": {
                "inputs": {"text": "text, watermark", "clip": ["4", 1]},
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "NegativePrompt"},
            },
            "8": {
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                "class_type": "VAEDecode",
                "_meta": {"title": "VAEDecode"},
            },
            "9": {
                "inputs": {"filename_prefix": "ComfyUI", "images": ["8", 0]},
                "class_type": "SaveImage",
                "_meta": {"title": "SaveImage"},
            },
        },
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)

    preset = GenerationPreset(
        name="Default portrait preset",
        description="Default generation preset for the text-to-image workflow.",
        status="active",
        version=1,
        workflow_template_id=workflow.id,
        checkpoint="Qwen-Rapid-AIO-NSFW-v11.safetensors",
        loras=[],
        width=512,
        height=512,
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
