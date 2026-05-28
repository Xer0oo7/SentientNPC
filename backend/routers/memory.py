from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Memory, NPC, get_db
from models import MemoryCreate, MemoryRead


router = APIRouter(tags=["memory"])


@router.post("/", response_model=MemoryRead)
def create_memory(payload: MemoryCreate, db: Session = Depends(get_db)):
    if not db.get(NPC, payload.npc_id):
        raise HTTPException(status_code=404, detail="NPC not found")
    memory = Memory(
        npc_id=payload.npc_id,
        event_type=payload.event_type,
        description=payload.description,
        location=payload.location,
        importance=payload.importance,
        is_longterm=payload.is_longterm or payload.importance >= 0.7,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


@router.get("/{npc_id}", response_model=list[MemoryRead])
def get_memories(
    npc_id: str,
    longterm_only: bool = False,
    min_importance: float | None = Query(default=None, ge=0, le=1),
    event_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if not db.get(NPC, npc_id):
        raise HTTPException(status_code=404, detail="NPC not found")
    query = db.query(Memory).filter(Memory.npc_id == npc_id)
    if longterm_only:
        query = query.filter(Memory.is_longterm.is_(True))
    if min_importance is not None:
        query = query.filter(Memory.importance >= min_importance)
    if event_type:
        query = query.filter(Memory.event_type == event_type)
    return query.order_by(Memory.timestamp.desc()).limit(limit).all()


@router.delete("/{npc_id}/shortterm")
def purge_shortterm_memories(npc_id: str, db: Session = Depends(get_db)):
    if not db.get(NPC, npc_id):
        raise HTTPException(status_code=404, detail="NPC not found")
    deleted = db.query(Memory).filter(Memory.npc_id == npc_id, Memory.is_longterm.is_(False)).delete()
    db.commit()
    return {"deleted": deleted, "npc_id": npc_id}


@router.get("/{npc_id}/summary")
def memory_summary(npc_id: str, db: Session = Depends(get_db)):
    if not db.get(NPC, npc_id):
        raise HTTPException(status_code=404, detail="NPC not found")
    total = db.query(func.count(Memory.id)).filter(Memory.npc_id == npc_id).scalar() or 0
    longterm = (
        db.query(func.count(Memory.id))
        .filter(Memory.npc_id == npc_id, Memory.is_longterm.is_(True))
        .scalar()
        or 0
    )
    average_importance = db.query(func.avg(Memory.importance)).filter(Memory.npc_id == npc_id).scalar()
    recent = (
        db.query(Memory)
        .filter(Memory.npc_id == npc_id)
        .order_by(Memory.timestamp.desc())
        .first()
    )
    return {
        "npc_id": npc_id,
        "total_memories": total,
        "longterm_memories": longterm,
        "average_importance": average_importance or 0.0,
        "most_recent_event_type": recent.event_type if recent else None,
    }
