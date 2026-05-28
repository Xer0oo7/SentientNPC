import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import NPC, get_db
from models import EmotionUpdate, NPCCreate, NPCRead, ReputationDelta


router = APIRouter(tags=["npc"])

ALLOWED_EMOTIONS = {"neutral", "happy", "sad", "angry", "fearful", "excited"}


def clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@router.post("/", response_model=NPCRead)
def create_npc(payload: NPCCreate, db: Session = Depends(get_db)):
    if payload.emotion not in ALLOWED_EMOTIONS:
        raise HTTPException(status_code=422, detail="Invalid emotion state")
    existing = db.get(NPC, payload.id)
    if existing:
        raise HTTPException(status_code=400, detail="NPC already exists")

    npc = NPC(
        id=payload.id,
        name=payload.name,
        personality=payload.personality.model_dump_json(),
        emotion=payload.emotion,
        reputation=clamp(payload.reputation),
        created_at=datetime.utcnow(),
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)
    return npc


@router.get("/", response_model=list[NPCRead])
def list_npcs(db: Session = Depends(get_db)):
    return db.query(NPC).order_by(NPC.created_at.asc()).all()


@router.get("/{npc_id}", response_model=NPCRead)
def get_npc(npc_id: str, db: Session = Depends(get_db)):
    npc = db.get(NPC, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")
    json.loads(npc.personality)
    return npc


@router.patch("/{npc_id}/emotion", response_model=NPCRead)
def update_emotion(npc_id: str, payload: EmotionUpdate, db: Session = Depends(get_db)):
    if payload.emotion not in ALLOWED_EMOTIONS:
        raise HTTPException(status_code=422, detail="Invalid emotion state")
    npc = db.get(NPC, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")
    npc.emotion = payload.emotion
    db.commit()
    db.refresh(npc)
    return npc


@router.patch("/{npc_id}/reputation", response_model=NPCRead)
def update_reputation(npc_id: str, payload: ReputationDelta, db: Session = Depends(get_db)):
    npc = db.get(NPC, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")
    npc.reputation = clamp(npc.reputation + payload.delta)
    db.commit()
    db.refresh(npc)
    return npc


@router.delete("/{npc_id}")
def delete_npc(npc_id: str, db: Session = Depends(get_db)):
    npc = db.get(NPC, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")
    db.delete(npc)
    db.commit()
    return {"deleted": True, "npc_id": npc_id}
