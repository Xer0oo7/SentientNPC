"""Tick-based simulation engine with per-NPC priority queues.

The engine runs as an asyncio background task inside FastAPI.
Each tick (default 200ms):
  1. Expire old short-term memories
  2. Run perception (vision scans for all NPCs)
  3. For each NPC, pop the highest-priority event from their queue
  4. Process the event: create memory, determine action, shift emotion
  5. Propagate sound if the event produces one
  6. Broadcast the processed event to all WebSocket subscribers
  7. Persist the event to the simulation_event audit log
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from database import SessionLocal
from database import NPC as NPCModel
from database import SimulationEvent
from event_bus import (
    EVENT_IMPORTANCE,
    EVENT_PRIORITY,
    PRIORITY_IDLE,
    PRIORITY_LABELS,
    EventBus,
    SimEvent,
)
from memory_manager import MemoryManager
from perception import SOUND_EVENTS

logger = logging.getLogger(__name__)


@dataclass(order=True)
class QueuedEvent:
    """A priority-queue entry. Lower priority number = processed first (min-heap)."""

    priority: int
    sequence: int = field(compare=True)  # tie-breaker: FIFO order
    npc_id: str = field(compare=False)
    event_type: str = field(compare=False)
    description: str = field(compare=False)
    location: Optional[str] = field(default=None, compare=False)
    importance: Optional[float] = field(default=None, compare=False)


# Personality-weighted action lookup: given an event, what does the NPC do?
# Format: {event_type: [(trait_check, action_if_true, action_if_false), ...]}
ACTION_RULES: dict[str, list[tuple[str, float, str, str]]] = {
    "player_stole": [
        ("aggressive", 60, "chase", "alert_guard"),
        ("bravery", 50, "confront", "report"),
    ],
    "player_attacked_ally": [
        ("bravery", 70, "attack", "flee"),
        ("aggressive", 50, "attack", "cower"),
    ],
    "npc_under_attack": [
        ("bravery", 40, "defend", "flee"),
    ],
    "threat_detected": [
        ("bravery", 60, "investigate", "hide"),
        ("curiosity", 50, "investigate", "ignore"),
    ],
    "sound_loud": [
        ("curiosity", 40, "investigate", "ignore"),
    ],
    "player_helped_npc": [
        ("friendly", 30, "thank", "acknowledge"),
    ],
    "player_completed_quest": [
        ("friendly", 20, "celebrate", "acknowledge"),
    ],
    "give_gift": [
        ("greedy", 60, "accept_eagerly", "accept"),
        ("friendly", 40, "thank", "accept"),
    ],
    "player_said_hello": [
        ("friendly", 50, "greet_warmly", "greet"),
    ],
    # Perception event actions
    "vision_spotted": [
        ("aggressive", 60, "watch_closely", "glance"),
        ("curiosity", 50, "observe", "ignore"),
    ],
    "sound_heard": [
        ("curiosity", 40, "investigate_sound", "stay_alert"),
        ("bravery", 60, "move_toward_sound", "stay_put"),
    ],
}

# Emotion shift rules: {event_type: [(emotion, intensity_threshold)]}
EMOTION_RULES: dict[str, list[tuple[str, float]]] = {
    "player_attacked_ally": [("angry", 0.8)],
    "npc_under_attack": [("fearful", 0.7), ("angry", 0.5)],
    "player_stole": [("angry", 0.6)],
    "threat_detected": [("fearful", 0.6)],
    "player_helped_npc": [("happy", 0.5)],
    "player_completed_quest": [("happy", 0.6), ("excited", 0.4)],
    "give_gift": [("happy", 0.5)],
    "player_said_hello": [("happy", 0.2)],
    # Perception emotion effects
    "vision_spotted": [("neutral", 0.1)],
    "sound_heard": [("fearful", 0.3)],
}


def _get_npc_personality(npc_id: str) -> dict[str, float]:
    """Fetch an NPC's personality traits from the database."""
    import json

    db = SessionLocal()
    try:
        npc = db.get(NPCModel, npc_id)
        if npc:
            return json.loads(npc.personality)
        return {}
    finally:
        db.close()


def _determine_action(
    event_type: str, personality: dict[str, float]
) -> str:
    """Pick an action based on event type and NPC personality traits."""
    rules = ACTION_RULES.get(event_type)
    if not rules:
        return "observe"

    for trait, threshold, action_true, action_false in rules:
        trait_value = personality.get(trait, 50)
        if trait_value >= threshold:
            return action_true
        return action_false

    return "observe"


def _determine_emotion_shift(
    event_type: str, current_emotion: str
) -> dict[str, str] | None:
    """Determine if the NPC's emotion should shift based on the event."""
    rules = EMOTION_RULES.get(event_type)
    if not rules:
        return None

    # Pick the highest-intensity emotion shift
    best_emotion, best_intensity = None, 0.0
    for emotion, intensity in rules:
        if intensity > best_intensity:
            best_emotion = emotion
            best_intensity = intensity

    if best_emotion and best_emotion != current_emotion:
        return {"from": current_emotion, "to": best_emotion}
    return None


def _update_npc_emotion(npc_id: str, new_emotion: str) -> None:
    """Update an NPC's emotion in the database."""
    db = SessionLocal()
    try:
        npc = db.get(NPCModel, npc_id)
        if npc:
            npc.emotion = new_emotion
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _get_npc_emotion(npc_id: str) -> str:
    """Get an NPC's current emotion from the database."""
    db = SessionLocal()
    try:
        npc = db.get(NPCModel, npc_id)
        return npc.emotion if npc else "neutral"
    finally:
        db.close()


class SimulationEngine:
    """Core tick-based simulation loop with per-NPC priority queues."""

    def __init__(
        self,
        event_bus: EventBus,
        memory_manager: MemoryManager,
        tick_interval_ms: int | None = None,
        world=None,
        perception_engine=None,
    ) -> None:
        self.event_bus = event_bus
        self.memory_manager = memory_manager
        self.tick_interval = (
            tick_interval_ms or int(os.getenv("TICK_INTERVAL_MS", "200"))
        ) / 1000.0
        self.tick_count: int = 0
        self.running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._sequence: int = 0  # global insertion counter for FIFO tie-breaking

        # Per-NPC priority queues: {npc_id: list[QueuedEvent]}  (heapq min-heap)
        self._queues: dict[str, list[QueuedEvent]] = {}

        # World state and perception engine (Cycle 2)
        self.world = world
        self.perception_engine = perception_engine

    @property
    def npc_ids(self) -> list[str]:
        """Return all NPC IDs that have a queue."""
        return list(self._queues.keys())

    def get_queue_depths(self) -> dict[str, int]:
        """Return {npc_id: queue_size} for all NPCs."""
        return {npc_id: len(q) for npc_id, q in self._queues.items()}

    def get_queue_snapshot(self, npc_id: str) -> list[dict[str, Any]]:
        """Return sorted snapshot of an NPC's queue (highest priority first)."""
        q = self._queues.get(npc_id, [])
        # heapq is a min-heap, so sorted order = priority order
        return [
            {
                "priority": e.priority,
                "priority_label": PRIORITY_LABELS.get(e.priority, "unknown"),
                "event_type": e.event_type,
                "description": e.description,
                "location": e.location,
            }
            for e in sorted(q)
        ]

    def enqueue_event(
        self,
        npc_id: str,
        event_type: str,
        description: str,
        priority: int | None = None,
        location: str | None = None,
        importance: float | None = None,
    ) -> None:
        """Add an event to an NPC's priority queue."""
        if priority is None:
            priority = EVENT_PRIORITY.get(event_type, PRIORITY_IDLE)
        if importance is None:
            importance = EVENT_IMPORTANCE.get(event_type, 0.3)

        if npc_id not in self._queues:
            self._queues[npc_id] = []

        self._sequence += 1
        event = QueuedEvent(
            priority=priority,
            sequence=self._sequence,
            npc_id=npc_id,
            event_type=event_type,
            description=description,
            location=location,
            importance=importance,
        )
        heapq.heappush(self._queues[npc_id], event)
        logger.debug(
            "Enqueued event for %s: %s (priority=%d)", npc_id, event_type, priority
        )

    def _init_npc_queues(self) -> None:
        """Initialize empty queues for all NPCs in the database."""
        db = SessionLocal()
        try:
            npcs = db.query(NPCModel).all()
            for npc in npcs:
                if npc.id not in self._queues:
                    self._queues[npc.id] = []
            logger.info("Initialized queues for %d NPCs", len(npcs))
        finally:
            db.close()

    def _init_world_entities(self) -> None:
        """Load NPC positions from DB into the world state."""
        if self.world is None:
            return

        db = SessionLocal()
        try:
            npcs = db.query(NPCModel).all()
            for npc in npcs:
                self.world.place_entity(
                    entity_id=npc.id,
                    entity_type="npc",
                    x=npc.pos_x,
                    z=npc.pos_z,
                    facing_angle=npc.facing_angle,
                    zone=npc.zone,
                )
                # Load perception config
                if self.perception_engine:
                    self.perception_engine.set_perception_config(
                        npc.id,
                        vision_range=npc.vision_range,
                        vision_fov=npc.vision_fov,
                        hearing_range=npc.hearing_range,
                    )
            # Place player entity at town square
            self.world.place_entity(
                entity_id="player_001",
                entity_type="player",
                x=0.0,
                z=0.0,
                facing_angle=0.0,
                zone="town_square",
            )
            logger.info(
                "World initialized with %d entities", self.world.entity_count
            )
        finally:
            db.close()

    async def start(self) -> None:
        """Start the simulation tick loop."""
        if self.running:
            logger.warning("Simulation already running")
            return

        self._init_npc_queues()
        self._init_world_entities()
        self.running = True
        self._task = asyncio.create_task(self._tick_loop())
        logger.info(
            "Simulation started (tick_interval=%.0fms, npcs=%d, world_entities=%d)",
            self.tick_interval * 1000,
            len(self._queues),
            self.world.entity_count if self.world else 0,
        )

    async def stop(self) -> None:
        """Stop the simulation tick loop."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Simulation stopped at tick %d", self.tick_count)

    async def _tick_loop(self) -> None:
        """Main loop: runs a tick every `tick_interval` seconds."""
        while self.running:
            tick_start = time.monotonic()
            try:
                await self._tick()
            except Exception:
                logger.exception("Error in tick %d", self.tick_count)

            # Sleep for the remaining tick budget
            elapsed = time.monotonic() - tick_start
            sleep_time = max(0, self.tick_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _tick(self) -> None:
        """Execute one simulation tick."""
        self.tick_count += 1

        # 1. Expire old short-term memories
        expired = self.memory_manager.expire_stm()
        if expired:
            logger.debug("STM expired: %s", expired)

        # 2. Run perception scans (vision detections)
        if self.perception_engine is not None:
            self.perception_engine.tick_perception(self.tick_count)

        # 3. Process one event per NPC (highest priority)
        for npc_id in list(self._queues.keys()):
            queue = self._queues[npc_id]
            if not queue:
                continue

            event = heapq.heappop(queue)
            await self._process_event(event)

    async def _process_event(self, event: QueuedEvent) -> None:
        """Process a single event: memory → decision → emotion → sound → broadcast."""
        npc_id = event.npc_id

        # 1. Create memory
        memory_created, is_longterm = self.memory_manager.add_memory(
            npc_id=npc_id,
            event_type=event.event_type,
            description=event.description,
            location=event.location,
            importance=event.importance,
        )

        # 2. Determine action based on personality
        personality = _get_npc_personality(npc_id)
        action = _determine_action(event.event_type, personality)

        # 3. Check for emotion shift
        current_emotion = _get_npc_emotion(npc_id)
        emotion_shift = _determine_emotion_shift(event.event_type, current_emotion)
        if emotion_shift:
            _update_npc_emotion(npc_id, emotion_shift["to"])

        # 4. Propagate sound if this event type produces one
        if self.perception_engine is not None and event.event_type in SOUND_EVENTS:
            self.perception_engine.propagate_sound(
                source_id=npc_id,
                event_type=event.event_type,
                current_tick=self.tick_count,
            )

        # 5. Build and broadcast SimEvent
        sim_event = SimEvent(
            tick=self.tick_count,
            npc_id=npc_id,
            event_type=event.event_type,
            priority=event.priority,
            description=event.description,
            action_taken=action,
            memory_created=memory_created,
            emotion_shift=emotion_shift,
        )
        await self.event_bus.broadcast(sim_event)

        # 6. Persist to simulation_event audit log
        self._persist_event(sim_event)

        logger.debug(
            "Tick %d | %s | %s → %s (emotion: %s)",
            self.tick_count,
            npc_id,
            event.event_type,
            action,
            emotion_shift or "unchanged",
        )

    @staticmethod
    def _persist_event(event: SimEvent) -> None:
        """Write processed event to the simulation_event audit table."""
        db = SessionLocal()
        try:
            row = SimulationEvent(
                tick=event.tick,
                npc_id=event.npc_id,
                event_type=event.event_type,
                priority=event.priority,
                action_taken=event.action_taken,
                description=event.description,
                timestamp=event.timestamp,
            )
            db.add(row)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist simulation event")
        finally:
            db.close()
