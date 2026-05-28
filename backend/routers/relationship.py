from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import NPC, Relationship, get_db
from models import RelationshipCreate, RelationshipDelta, RelationshipRead, RelationshipWithLabel


router = APIRouter(tags=["relationship"])


def clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def relationship_label(score: float) -> str:
    if score == 100:
        return "best_friend"
    if score < -50:
        return "enemy"
    if score < 0:
        return "hostile"
    if score > 50:
        return "friendly"
    return "neutral"


@router.post("/", response_model=RelationshipRead)
def upsert_relationship(payload: RelationshipCreate, db: Session = Depends(get_db)):
    if not db.get(NPC, payload.npc_id):
        raise HTTPException(status_code=404, detail="NPC not found")
    relationship = (
        db.query(Relationship)
        .filter(Relationship.npc_id == payload.npc_id, Relationship.player_id == payload.player_id)
        .first()
    )
    if relationship:
        relationship.score = clamp(payload.score)
        relationship.updated_at = datetime.utcnow()
    else:
        relationship = Relationship(
            npc_id=payload.npc_id,
            player_id=payload.player_id,
            score=clamp(payload.score),
            updated_at=datetime.utcnow(),
        )
        db.add(relationship)
    db.commit()
    db.refresh(relationship)
    return relationship


@router.get("/{npc_id}/{player_id}", response_model=RelationshipWithLabel)
def get_relationship(npc_id: str, player_id: str, db: Session = Depends(get_db)):
    relationship = (
        db.query(Relationship)
        .filter(Relationship.npc_id == npc_id, Relationship.player_id == player_id)
        .first()
    )
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {**RelationshipRead.model_validate(relationship).model_dump(), "label": relationship_label(relationship.score)}


@router.patch("/{npc_id}/{player_id}", response_model=RelationshipWithLabel)
def update_relationship(npc_id: str, player_id: str, payload: RelationshipDelta, db: Session = Depends(get_db)):
    relationship = (
        db.query(Relationship)
        .filter(Relationship.npc_id == npc_id, Relationship.player_id == player_id)
        .first()
    )
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    relationship.score = clamp(relationship.score + payload.delta)
    relationship.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(relationship)
    return {**RelationshipRead.model_validate(relationship).model_dump(), "label": relationship_label(relationship.score)}


@router.get("/{npc_id}", response_model=list[RelationshipWithLabel])
def list_relationships(npc_id: str, db: Session = Depends(get_db)):
    if not db.get(NPC, npc_id):
        raise HTTPException(status_code=404, detail="NPC not found")
    relationships = db.query(Relationship).filter(Relationship.npc_id == npc_id).all()
    return [
        {**RelationshipRead.model_validate(relationship).model_dump(), "label": relationship_label(relationship.score)}
        for relationship in relationships
    ]
