from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import (
    Character,
    CharacterProfile,
    CharacterPrompt,
    CharacterVisual,
    GenerationPreset,
    utc_now,
)
from app.responses import ApiError
from app.schemas import CharacterUpsert


def get_character(session: Session, character_id: str) -> Character:
    character = session.get(Character, character_id)
    if not character:
        raise ApiError("CHARACTER_NOT_FOUND", "Character not found", 404)
    return character


def get_default_character(session: Session) -> Character:
    character = session.exec(
        select(Character).where(Character.is_default == True).order_by(Character.created_at)  # noqa: E712
    ).first()
    if not character:
        raise ApiError("CHARACTER_NOT_FOUND", "Default character not found", 404)
    return character


def get_profile(session: Session, profile_id: str | None) -> CharacterProfile:
    if not profile_id:
        raise ApiError("CHARACTER_PROFILE_REQUIRED", "Character profile is required", 400)
    profile = session.get(CharacterProfile, profile_id)
    if not profile:
        raise ApiError("CHARACTER_PROFILE_REQUIRED", "Character profile is required", 400)
    return profile


def get_prompt(session: Session, prompt_id: str | None) -> CharacterPrompt:
    if not prompt_id:
        raise ApiError("CHARACTER_PROMPT_REQUIRED", "Character prompt is required", 400)
    prompt = session.get(CharacterPrompt, prompt_id)
    if not prompt:
        raise ApiError("CHARACTER_PROMPT_REQUIRED", "Character prompt is required", 400)
    return prompt


def get_visual(session: Session, visual_id: str | None) -> CharacterVisual:
    if not visual_id:
        raise ApiError("CHARACTER_VISUAL_REQUIRED", "Character visual is required", 400)
    visual = session.get(CharacterVisual, visual_id)
    if not visual:
        raise ApiError("CHARACTER_VISUAL_REQUIRED", "Character visual is required", 400)
    return visual


def character_bundle(session: Session, character: Character) -> dict[str, Any]:
    return {
        "character": character,
        "profile": get_profile(session, character.profile_id),
        "prompt": get_prompt(session, character.prompt_id),
        "visual": get_visual(session, character.visual_id),
    }


def create_character(session: Session, payload: CharacterUpsert) -> dict[str, Any]:
    existing = session.exec(select(Character).where(Character.code == payload.code)).first()
    if existing:
        raise ApiError("CONFLICT", "Character code already exists", 409)

    character = Character(code=payload.code, status="draft", version=1, is_default=False)
    session.add(character)
    session.commit()
    session.refresh(character)

    profile = CharacterProfile(
        character_id=character.id,
        name=payload.profile.name,
        avatar_url=payload.profile.avatarUrl,
        description=payload.profile.description,
        personality=payload.profile.personality,
        scenario=payload.profile.scenario,
        first_message=payload.profile.firstMessage,
        tags=payload.profile.tags,
    )
    prompt = CharacterPrompt(
        character_id=character.id,
        system_prompt=payload.prompt.systemPrompt,
        roleplay_prompt=payload.prompt.roleplayPrompt,
        conversation_style=payload.prompt.conversationStyle,
        safety_prompt=payload.prompt.safetyPrompt,
    )
    visual = CharacterVisual(
        character_id=character.id,
        visual_prompt=payload.visual.visualPrompt,
        visual_negative_prompt=payload.visual.visualNegativePrompt,
        generation_preset_id=payload.visual.generationPresetId,
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
    session.refresh(character)
    return character_bundle(session, character)


def update_character(session: Session, character_id: str, payload: CharacterUpsert) -> dict[str, Any]:
    character = get_character(session, character_id)
    duplicate = session.exec(select(Character).where(Character.code == payload.code)).first()
    if duplicate and duplicate.id != character_id:
        raise ApiError("CONFLICT", "Character code already exists", 409)

    character.code = payload.code
    character.version += 1
    character.updated_at = utc_now()

    profile = get_profile(session, character.profile_id)
    profile.name = payload.profile.name
    profile.avatar_url = payload.profile.avatarUrl
    profile.description = payload.profile.description
    profile.personality = payload.profile.personality
    profile.scenario = payload.profile.scenario
    profile.first_message = payload.profile.firstMessage
    profile.tags = payload.profile.tags
    profile.updated_at = utc_now()

    prompt = get_prompt(session, character.prompt_id)
    prompt.system_prompt = payload.prompt.systemPrompt
    prompt.roleplay_prompt = payload.prompt.roleplayPrompt
    prompt.conversation_style = payload.prompt.conversationStyle
    prompt.safety_prompt = payload.prompt.safetyPrompt
    prompt.updated_at = utc_now()

    visual = get_visual(session, character.visual_id)
    visual.visual_prompt = payload.visual.visualPrompt
    visual.visual_negative_prompt = payload.visual.visualNegativePrompt
    visual.generation_preset_id = payload.visual.generationPresetId
    visual.updated_at = utc_now()

    session.add(character)
    session.add(profile)
    session.add(prompt)
    session.add(visual)
    session.commit()
    session.refresh(character)
    return character_bundle(session, character)


def publish_character(session: Session, character_id: str) -> dict[str, Any]:
    character = get_character(session, character_id)
    profile = get_profile(session, character.profile_id)
    get_prompt(session, character.prompt_id)
    visual = get_visual(session, character.visual_id)
    preset = session.get(GenerationPreset, visual.generation_preset_id)
    if not preset:
        raise ApiError("GENERATION_PRESET_NOT_FOUND", "Generation preset not found", 404)
    if not profile.name:
        raise ApiError("CHARACTER_PROFILE_REQUIRED", "Character profile name is required", 400)

    character.status = "active"
    character.version += 1
    character.published_at = datetime.now(timezone.utc)
    character.updated_at = utc_now()
    session.add(character)
    session.commit()
    session.refresh(character)
    return character_bundle(session, character)
