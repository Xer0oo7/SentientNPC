import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import DialogueLog, Memory, NPC, Relationship, SimulationEvent, get_db
from models import DialogueLogRead, MemoryRead, RelationshipRead
from routers.relationship import relationship_label


router = APIRouter(tags=["analytics"])


@router.get("/overview")
def analytics_overview(db: Session = Depends(get_db)):
    npcs = db.query(NPC).order_by(NPC.created_at.asc()).all()
    return [
        {
            "id": npc.id,
            "name": npc.name,
            "emotion": npc.emotion,
            "fsm_state": npc.fsm_state,
            "reputation": npc.reputation,
            "memory_count": db.query(func.count(Memory.id)).filter(Memory.npc_id == npc.id).scalar() or 0,
            "relationship_count": db.query(func.count(Relationship.player_id)).filter(Relationship.npc_id == npc.id).scalar()
            or 0,
        }
        for npc in npcs
    ]


@router.get("/npc/{npc_id}")
def npc_analytics(npc_id: str, db: Session = Depends(get_db)):
    npc = db.get(NPC, npc_id)
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    memories = db.query(Memory).filter(Memory.npc_id == npc_id).order_by(Memory.timestamp.desc()).all()
    relationships = db.query(Relationship).filter(Relationship.npc_id == npc_id).all()
    recent_dialogue = (
        db.query(DialogueLog)
        .filter(DialogueLog.npc_id == npc_id)
        .order_by(DialogueLog.timestamp.desc())
        .limit(20)
        .all()
    )

    return {
        "id": npc.id,
        "name": npc.name,
        "personality": json.loads(npc.personality),
        "emotion": npc.emotion,
        "fsm_state": npc.fsm_state,
        "reputation": npc.reputation,
        "memories": [MemoryRead.model_validate(memory).model_dump() for memory in memories],
        "relationships": [
            {**RelationshipRead.model_validate(relationship).model_dump(), "label": relationship_label(relationship.score)}
            for relationship in relationships
        ],
        "recent_dialogue_count": len(recent_dialogue),
        "recent_dialogue": [DialogueLogRead.model_validate(log).model_dump() for log in recent_dialogue],
        "last_event_type": (
            db.query(SimulationEvent.event_type)
            .filter(SimulationEvent.npc_id == npc_id)
            .order_by(SimulationEvent.tick.desc(), SimulationEvent.timestamp.desc())
            .limit(1)
            .scalar()
        ),
        "last_action_taken": (
            db.query(SimulationEvent.action_taken)
            .filter(SimulationEvent.npc_id == npc_id)
            .order_by(SimulationEvent.tick.desc(), SimulationEvent.timestamp.desc())
            .limit(1)
            .scalar()
        ),
    }
