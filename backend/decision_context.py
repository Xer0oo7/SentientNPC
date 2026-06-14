"""Decision-context assembly for behavior tree evaluation.

The context collects the small amount of state needed for the BT layer:
- NPC personality, emotion, FSM state, and reputation
- recent memories and relationship score
- nearby world entities when a world state is available

This keeps behavior tree predicates simple and avoids repeated database reads
inside individual condition nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from database import NPC as NPCModel
from database import Relationship, SessionLocal


@dataclass
class DecisionContext:
    npc_id: str
    event_type: str
    description: str
    priority: int
    importance: float
    location: Optional[str]
    personality: dict[str, float]
    emotion: str
    fsm_state: str
    reputation: float
    relationship_score: float
    current_zone: Optional[str]
    position: tuple[float, float]
    recent_memories: list[dict[str, Any]] = field(default_factory=list)
    nearby_entities: list[dict[str, Any]] = field(default_factory=list)

    def trait(self, name: str, default: float = 50.0) -> float:
        return float(self.personality.get(name, default))

    def has_recent_event(self, event_type: str, limit: int = 5) -> bool:
        return any(memory.get("event_type") == event_type for memory in self.recent_memories[:limit])

    def has_recent_high_importance_event(self, event_type: str, threshold: float = 0.7) -> bool:
        return any(
            memory.get("event_type") == event_type and float(memory.get("importance", 0.0)) >= threshold
            for memory in self.recent_memories
        )

    def nearby_entity_ids(self, entity_type: Optional[str] = None) -> list[str]:
        if entity_type is None:
            return [entity["id"] for entity in self.nearby_entities]
        return [entity["id"] for entity in self.nearby_entities if entity.get("entity_type") == entity_type]

    def recent_event_types(self) -> list[str]:
        return [memory.get("event_type", "") for memory in self.recent_memories]


def _get_relationship_score(db, npc_id: str) -> float:
    relationship = (
        db.query(Relationship)
        .filter(Relationship.npc_id == npc_id, Relationship.player_id == "player_001")
        .first()
    )
    if relationship is not None:
        return float(relationship.score)

    relationship = (
        db.query(Relationship)
        .filter(Relationship.npc_id == npc_id)
        .order_by(Relationship.updated_at.desc())
        .first()
    )
    return float(relationship.score) if relationship is not None else 0.0


def _get_recent_memories(memory_manager: Any, npc_id: str, limit: int = 8) -> list[dict[str, Any]]:
    if memory_manager is None:
        return []
    try:
        return memory_manager.query_recent(npc_id, limit=limit)
    except Exception:
        return []


def _get_nearby_entities(world: Any, npc_row: Any) -> list[dict[str, Any]]:
    if world is None or npc_row is None:
        return []

    entity = world.get_entity(npc_row.id)
    if entity is None:
        return []

    search_radius = max(float(npc_row.vision_range or 0.0), float(npc_row.hearing_range or 0.0))
    nearby: list[dict[str, Any]] = []
    for other, distance in world.get_entities_in_radius(entity.x, entity.z, search_radius, exclude_id=entity.id):
        nearby.append(
            {
                "id": other.id,
                "entity_type": other.entity_type,
                "distance": round(distance, 2),
                "zone": other.zone,
            }
        )
    return nearby


def build_decision_context(
    npc_id: str,
    event_type: str,
    description: str,
    priority: int,
    importance: float,
    location: Optional[str],
    memory_manager: Any = None,
    world: Any = None,
) -> DecisionContext:
    """Assemble the decision context for a single queued event."""

    db = SessionLocal()
    try:
        npc_row = db.get(NPCModel, npc_id)
        if npc_row is None:
            return DecisionContext(
                npc_id=npc_id,
                event_type=event_type,
                description=description,
                priority=priority,
                importance=importance,
                location=location,
                personality={},
                emotion="neutral",
                fsm_state="idle",
                reputation=0.0,
                relationship_score=0.0,
                current_zone=None,
                position=(0.0, 0.0),
                recent_memories=_get_recent_memories(memory_manager, npc_id),
                nearby_entities=[],
            )

        import json

        nearby_entities = _get_nearby_entities(world, npc_row)
        return DecisionContext(
            npc_id=npc_row.id,
            event_type=event_type,
            description=description,
            priority=priority,
            importance=importance,
            location=location,
            personality=json.loads(npc_row.personality),
            emotion=npc_row.emotion,
            fsm_state=npc_row.fsm_state,
            reputation=float(npc_row.reputation),
            relationship_score=_get_relationship_score(db, npc_row.id),
            current_zone=npc_row.zone,
            position=(float(npc_row.pos_x), float(npc_row.pos_z)),
            recent_memories=_get_recent_memories(memory_manager, npc_row.id),
            nearby_entities=nearby_entities,
        )
    finally:
        db.close()
