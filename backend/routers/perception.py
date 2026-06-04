"""Perception system API endpoints.

Endpoints:
  GET   /perception/world               — Full world state snapshot
  PATCH /perception/move/{entity_id}     — Move an entity to new position
  GET   /perception/fov/{npc_id}         — Get NPC's vision cone data
  GET   /perception/nearby/{npc_id}      — Get entities within perception range
  POST  /perception/sound               — Manually trigger a sound at a position
  GET   /perception/config/{npc_id}      — Get NPC perception config
  PATCH /perception/config/{npc_id}      — Update NPC perception config
  GET   /perception/events               — Recent perception events
"""

from __future__ import annotations

from fastapi import APIRouter

from models import PerceptionConfigUpdate, PositionUpdate, SoundTrigger

router = APIRouter(tags=["perception"])

# Injected by main.py at startup
_world = None
_perception_engine = None
_sim_engine = None


def set_perception(world, perception_engine, sim_engine):
    """Called by main.py to inject shared instances."""
    global _world, _perception_engine, _sim_engine
    _world = world
    _perception_engine = perception_engine
    _sim_engine = sim_engine


@router.get("/world")
def get_world_snapshot():
    """Return the full world state: all entities and zones."""
    if _world is None:
        return {"error": "World not initialized"}
    return _world.get_snapshot()


@router.patch("/move/{entity_id}")
def move_entity(entity_id: str, payload: PositionUpdate):
    """Move an entity to a new position."""
    if _world is None:
        return {"error": "World not initialized"}

    entity = _world.move_entity(
        entity_id,
        x=payload.x,
        z=payload.z,
        facing_angle=payload.facing_angle,
        zone=payload.zone,
    )
    if entity is None:
        return {"error": f"Entity '{entity_id}' not found"}

    # Also update DB if it's an NPC
    if entity.entity_type == "npc":
        _update_npc_position_in_db(
            entity_id, payload.x, payload.z,
            payload.facing_angle, entity.zone,
        )

    return {
        "status": "moved",
        "entity": entity.to_dict(),
    }


@router.get("/fov/{npc_id}")
def get_npc_fov(npc_id: str):
    """Return vision cone visualization data for an NPC."""
    if _perception_engine is None:
        return {"error": "Perception engine not initialized"}

    fov_data = _perception_engine.get_npc_fov_data(npc_id)
    if fov_data is None:
        return {"error": f"NPC '{npc_id}' not found"}
    return fov_data


@router.get("/nearby/{npc_id}")
def get_nearby_entities(npc_id: str):
    """Return all entities near an NPC with visibility status."""
    if _perception_engine is None:
        return {"error": "Perception engine not initialized"}

    result = _perception_engine.get_nearby_entities(npc_id)
    if result is None:
        return {"error": f"NPC '{npc_id}' not found"}
    return result


@router.post("/sound")
def trigger_sound(payload: SoundTrigger):
    """Manually trigger a sound at a position, propagated to all NPCs in range."""
    if _perception_engine is None or _sim_engine is None:
        return {"error": "Perception engine not initialized"}

    # Map sound_type to an event_type that exists in SOUND_EVENTS
    # If the sound_type doesn't match, use "sound_loud" as default
    from perception import SOUND_EVENTS
    event_type = None
    for et, config in SOUND_EVENTS.items():
        if config["sound_type"] == payload.sound_type:
            event_type = et
            break
    if event_type is None:
        event_type = "sound_loud"

    events = _perception_engine.propagate_sound(
        source_id="manual_trigger",
        event_type=event_type,
        current_tick=_sim_engine.tick_count,
        source_x=payload.x,
        source_z=payload.z,
    )

    return {
        "status": "propagated",
        "sound_type": payload.sound_type,
        "position": {"x": payload.x, "z": payload.z},
        "npcs_affected": len(events),
        "events": events,
    }


@router.get("/config/{npc_id}")
def get_perception_config(npc_id: str):
    """Get an NPC's perception configuration."""
    if _perception_engine is None:
        return {"error": "Perception engine not initialized"}
    return {
        "npc_id": npc_id,
        "config": _perception_engine.get_perception_config(npc_id),
    }


@router.patch("/config/{npc_id}")
def update_perception_config(npc_id: str, payload: PerceptionConfigUpdate):
    """Update an NPC's perception configuration."""
    if _perception_engine is None:
        return {"error": "Perception engine not initialized"}

    config = _perception_engine.set_perception_config(
        npc_id,
        vision_range=payload.vision_range,
        vision_fov=payload.vision_fov,
        hearing_range=payload.hearing_range,
    )

    # Update DB
    _update_npc_perception_config_in_db(
        npc_id,
        payload.vision_range,
        payload.vision_fov,
        payload.hearing_range,
    )

    return {
        "status": "updated",
        "npc_id": npc_id,
        "config": config,
    }


@router.get("/events")
def recent_perception_events(limit: int = 50):
    """Return recent perception events (newest first)."""
    if _perception_engine is None:
        return []
    return _perception_engine.get_recent_perception_events(limit)


def _update_npc_position_in_db(
    npc_id: str, x: float, z: float,
    facing_angle: float | None, zone: str | None,
) -> None:
    """Persist NPC position change to the database."""
    from database import SessionLocal, NPC
    db = SessionLocal()
    try:
        npc = db.get(NPC, npc_id)
        if npc:
            npc.pos_x = x
            npc.pos_z = z
            if facing_angle is not None:
                npc.facing_angle = facing_angle
            if zone is not None:
                npc.zone = zone
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _update_npc_perception_config_in_db(
    npc_id: str,
    vision_range: float | None,
    vision_fov: float | None,
    hearing_range: float | None,
) -> None:
    """Persist NPC perception config change to the database."""
    from database import SessionLocal, NPC
    db = SessionLocal()
    try:
        npc = db.get(NPC, npc_id)
        if npc:
            if vision_range is not None:
                npc.vision_range = vision_range
            if vision_fov is not None:
                npc.vision_fov = vision_fov
            if hearing_range is not None:
                npc.hearing_range = hearing_range
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
