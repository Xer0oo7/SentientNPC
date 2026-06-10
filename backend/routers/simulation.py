"""Simulation control endpoints and WebSocket event stream.

Endpoints:
  POST /simulation/start       — Start the tick engine
  POST /simulation/stop        — Stop the tick engine
  GET  /simulation/status      — Current tick, running state, queue depths
  POST /simulation/inject      — Inject event into an NPC's priority queue
  GET  /simulation/events      — Recent event history (REST fallback)
  GET  /simulation/queues      — Snapshot of all NPC queues
  GET  /simulation/queues/{id} — Snapshot of a single NPC's queue
  GET  /simulation/memory/{id} — STM snapshot for an NPC
  WS   /simulation/ws          — Live event stream
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import NPC, SimulationEvent, get_db
from event_bus import EVENT_PRIORITY, PRIORITY_LOW
from fsm import FSM_STATES
from models import DecisionStateRead

router = APIRouter(tags=["simulation"])

# These will be injected by main.py at startup
_engine = None
_event_bus = None
_memory_manager = None


def set_engine(engine, event_bus, memory_manager):
    """Called by main.py to inject shared instances."""
    global _engine, _event_bus, _memory_manager
    _engine = engine
    _event_bus = event_bus
    _memory_manager = memory_manager


class InjectEventPayload(BaseModel):
    npc_id: str
    event_type: str
    description: str
    priority: Optional[int] = Field(default=None, ge=0, le=4)
    location: Optional[str] = None
    importance: Optional[float] = Field(default=None, ge=0, le=1)


@router.post("/start")
async def start_simulation():
    if _engine is None:
        return {"error": "Engine not initialized"}
    if _engine.running:
        return {"status": "already_running", "tick": _engine.tick_count}
    await _engine.start()
    return {"status": "started", "tick_interval_ms": int(_engine.tick_interval * 1000)}


@router.post("/stop")
async def stop_simulation():
    if _engine is None:
        return {"error": "Engine not initialized"}
    if not _engine.running:
        return {"status": "already_stopped", "tick": _engine.tick_count}
    await _engine.stop()
    return {"status": "stopped", "final_tick": _engine.tick_count}


@router.get("/status")
def simulation_status():
    if _engine is None:
        return {"error": "Engine not initialized"}
    result = {
        "running": _engine.running,
        "tick": _engine.tick_count,
        "tick_interval_ms": int(_engine.tick_interval * 1000),
        "queue_depths": _engine.get_queue_depths(),
        "stm_counts": _memory_manager.get_all_stm_counts() if _memory_manager else {},
        "ws_subscribers": _event_bus.subscriber_count if _event_bus else 0,
    }
    # Add world state info if available
    if _engine.world is not None:
        result["world_entities"] = _engine.world.entity_count
    if _engine.perception_engine is not None:
        result["perception_events_recent"] = len(
            _engine.perception_engine.get_recent_perception_events(limit=100)
        )
    return result

MAX_QUEUE_DEPTH = 50  # Reject injection if queue is already this deep


@router.get("/state/{npc_id}", response_model=DecisionStateRead)
def decision_state(npc_id: str, db: Session = Depends(get_db)):
    npc = db.get(NPC, npc_id)
    if not npc:
        return {
            "npc_id": npc_id,
            "fsm_state": "idle",
            "emotion": "neutral",
            "last_event_type": None,
            "last_action_taken": None,
            "last_tick": None,
            "available_states": list(FSM_STATES),
        }

    latest_event = (
        db.query(SimulationEvent)
        .filter(SimulationEvent.npc_id == npc_id)
        .order_by(SimulationEvent.tick.desc(), SimulationEvent.timestamp.desc())
        .first()
    )

    return {
        "npc_id": npc.id,
        "fsm_state": npc.fsm_state,
        "emotion": npc.emotion,
        "last_event_type": latest_event.event_type if latest_event else None,
        "last_action_taken": latest_event.action_taken if latest_event else None,
        "last_tick": latest_event.tick if latest_event else None,
        "available_states": list(FSM_STATES),
    }


@router.post("/inject")
def inject_event(payload: InjectEventPayload):
    if _engine is None:
        return {"error": "Engine not initialized"}

    # Validate event type against known types
    known_types = set(EVENT_PRIORITY.keys())
    if payload.event_type not in known_types:
        return {
            "error": f"Unknown event_type '{payload.event_type}'",
            "valid_types": sorted(known_types),
        }

    # Guard against queue flooding
    current_depth = len(_engine._queues.get(payload.npc_id, []))
    if current_depth >= MAX_QUEUE_DEPTH:
        return {
            "error": "Queue depth limit reached",
            "npc_id": payload.npc_id,
            "queue_depth": current_depth,
            "max_depth": MAX_QUEUE_DEPTH,
        }

    priority = payload.priority
    if priority is None:
        priority = EVENT_PRIORITY.get(payload.event_type, PRIORITY_LOW)

    _engine.enqueue_event(
        npc_id=payload.npc_id,
        event_type=payload.event_type,
        description=payload.description,
        priority=priority,
        location=payload.location,
        importance=payload.importance,
    )
    return {
        "status": "enqueued",
        "npc_id": payload.npc_id,
        "event_type": payload.event_type,
        "priority": priority,
        "queue_depth": len(_engine._queues.get(payload.npc_id, [])),
    }


@router.get("/events")
def recent_events(limit: int = 50):
    """REST fallback for recent events (newest first)."""
    if _event_bus is None:
        return []
    events = _event_bus.recent_events
    return events[:limit]


@router.get("/queues")
def all_queue_snapshots():
    """Return queue snapshots for all NPCs."""
    if _engine is None:
        return {}
    result = {}
    for npc_id in _engine.npc_ids:
        result[npc_id] = _engine.get_queue_snapshot(npc_id)
    return result


@router.get("/queues/{npc_id}")
def npc_queue_snapshot(npc_id: str):
    """Return queue snapshot for a specific NPC."""
    if _engine is None:
        return {"events": []}
    return {"npc_id": npc_id, "events": _engine.get_queue_snapshot(npc_id)}


@router.get("/memory/{npc_id}")
def npc_stm_snapshot(npc_id: str):
    """Return short-term memory snapshot for an NPC."""
    if _memory_manager is None:
        return {"npc_id": npc_id, "stm": []}
    return {
        "npc_id": npc_id,
        "stm": _memory_manager.get_stm_snapshot(npc_id),
        "stm_ttl": _memory_manager.stm_ttl,
        "stm_capacity": _memory_manager.stm_capacity,
    }


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for live event streaming to dashboard clients."""
    await ws.accept()
    await _event_bus.subscribe(ws)
    try:
        # Keep connection alive — client sends pings, we just wait
        while True:
            # Wait for any message from the client (ping/pong or close)
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await _event_bus.unsubscribe(ws)
