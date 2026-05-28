import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import DialogueLog, Memory, NPC, Relationship, get_db
from models import DialogueLogRead, DialogueRequest, DialogueResponse
from routers.relationship import relationship_label


router = APIRouter(tags=["dialogue"])

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"


def npc_role_from_name(name: str) -> str:
    return name.strip().lower().replace("_", " ") or "npc"


def fallback_response(label: str, emotion: str) -> str:
    if label == "best_friend":
        return "For you, my trusted friend, I will always spare a moment."
    if label == "friendly":
        return "Good to see you again. Speak freely, and I will listen."
    if label == "enemy":
        return "You are not welcome here. Say what you must and leave."
    if label == "hostile":
        return "I have not forgotten your choices. Make this quick."
    if emotion == "angry":
        return "Now is not the time to test my patience."
    if emotion == "fearful":
        return "Keep your voice low. These are uneasy times."
    if emotion == "happy":
        return "A fine day for conversation. What brings you to me?"
    return "I hear you. Tell me what you need."


def build_prompt(npc: NPC, relationship_score: float, label: str, memories: list[Memory], player_message: str) -> str:
    personality = json.loads(npc.personality)
    memory_lines = [
        f"- {memory.event_type}: {memory.description}"
        for memory in memories
    ]
    if not memory_lines:
        memory_lines = ["- No relevant memories."]
    return f"""You are {npc.name}, a {npc_role_from_name(npc.name)} in a medieval fantasy world.

Your personality: aggressive={personality.get("aggressive", 0)}/100, friendly={personality.get("friendly", 0)}/100, greedy={personality.get("greedy", 0)}/100, bravery={personality.get("bravery", 0)}/100
Your current emotion: {npc.emotion}
Your relationship with this player: {relationship_score}/100 ({label})

Your most relevant memories of this player:
{chr(10).join(memory_lines)}

The player says: "{player_message}"

Respond in character. One to two sentences only. Do not break character. Do not describe actions."""


async def call_ollama(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        response.raise_for_status()
        data = response.json()
        return (data.get("response") or "").strip()


@router.post("/{npc_id}", response_model=DialogueResponse)
async def dialogue(npc_id: str, payload: DialogueRequest, db: Session = Depends(get_db)):
    npc = db.get(NPC, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    relationship = (
        db.query(Relationship)
        .filter(Relationship.npc_id == npc_id, Relationship.player_id == payload.player_id)
        .first()
    )
    relationship_score = relationship.score if relationship else 0.0
    label = relationship_label(relationship_score)
    memories = (
        db.query(Memory)
        .filter(Memory.npc_id == npc_id)
        .order_by(Memory.importance.desc(), Memory.timestamp.desc())
        .limit(5)
        .all()
    )
    prompt = build_prompt(npc, relationship_score, label, memories, payload.player_message)

    try:
        npc_response = await call_ollama(prompt)
        if not npc_response:
            npc_response = fallback_response(label, npc.emotion)
    except httpx.HTTPError:
        npc_response = fallback_response(label, npc.emotion)

    log = DialogueLog(
        npc_id=npc_id,
        player_id=payload.player_id,
        player_message=payload.player_message,
        npc_response=npc_response,
        prompt=prompt,
    )
    db.add(log)
    db.commit()

    return {
        "npc_id": npc_id,
        "response": npc_response,
        "emotion": npc.emotion,
        "relationship_score": relationship_score,
    }


@router.get("/{npc_id}/history", response_model=list[DialogueLogRead])
def dialogue_history(npc_id: str, db: Session = Depends(get_db)):
    if not db.get(NPC, npc_id):
        raise HTTPException(status_code=404, detail="NPC not found")
    return (
        db.query(DialogueLog)
        .filter(DialogueLog.npc_id == npc_id)
        .order_by(DialogueLog.timestamp.desc())
        .limit(20)
        .all()
    )
