"""WebSocket event broadcaster for real-time simulation events.

The EventBus manages a set of WebSocket subscribers (dashboard clients)
and broadcasts simulation events as JSON to all of them. If a subscriber
disconnects or errors, it is silently removed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class SimEvent:
    """A single simulation event emitted by the tick engine."""

    __slots__ = (
        "tick",
        "timestamp",
        "npc_id",
        "event_type",
        "priority",
        "action_taken",
        "memory_created",
        "emotion_shift",
        "description",
    )

    def __init__(
        self,
        tick: int,
        npc_id: str,
        event_type: str,
        priority: int,
        description: str,
        action_taken: str | None = None,
        memory_created: bool = False,
        emotion_shift: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ):
        self.tick = tick
        self.timestamp = timestamp or datetime.utcnow()
        self.npc_id = npc_id
        self.event_type = event_type
        self.priority = priority
        self.action_taken = action_taken
        self.memory_created = memory_created
        self.emotion_shift = emotion_shift
        self.description = description

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "timestamp": self.timestamp.isoformat(),
            "npc_id": self.npc_id,
            "event_type": self.event_type,
            "priority": self.priority,
            "priority_label": PRIORITY_LABELS.get(self.priority, "unknown"),
            "action_taken": self.action_taken,
            "memory_created": self.memory_created,
            "emotion_shift": self.emotion_shift,
            "description": self.description,
        }


# Priority constants — lower number = higher priority
PRIORITY_CRITICAL = 0
PRIORITY_HIGH = 1
PRIORITY_MEDIUM = 2
PRIORITY_LOW = 3
PRIORITY_IDLE = 4

PRIORITY_LABELS = {
    0: "CRITICAL",
    1: "HIGH",
    2: "MEDIUM",
    3: "LOW",
    4: "IDLE",
}


# Default importance mapping for event types
EVENT_IMPORTANCE: dict[str, float] = {
    "player_attacked_ally": 0.9,
    "npc_under_attack": 0.95,
    "player_stole": 0.8,
    "threat_detected": 0.75,
    "sound_loud": 0.6,
    "player_helped_npc": 0.7,
    "player_completed_quest": 0.6,
    "give_gift": 0.5,
    "player_said_hello": 0.1,
    "ambient_observation": 0.05,
    "npc_idle_thought": 0.02,
    "schedule_check": 0.03,
    # Perception events
    "vision_spotted": 0.4,
    "sound_heard": 0.5,
    "entity_entered_zone": 0.3,
    "entity_left_zone": 0.2,
}

# Default priority mapping for event types
EVENT_PRIORITY: dict[str, int] = {
    "player_attacked_ally": PRIORITY_CRITICAL,
    "npc_under_attack": PRIORITY_CRITICAL,
    "player_stole": PRIORITY_HIGH,
    "threat_detected": PRIORITY_HIGH,
    "sound_loud": PRIORITY_HIGH,
    "player_helped_npc": PRIORITY_MEDIUM,
    "player_completed_quest": PRIORITY_MEDIUM,
    "give_gift": PRIORITY_MEDIUM,
    "player_said_hello": PRIORITY_LOW,
    "ambient_observation": PRIORITY_IDLE,
    "npc_idle_thought": PRIORITY_IDLE,
    "schedule_check": PRIORITY_IDLE,
    # Perception events
    "vision_spotted": PRIORITY_MEDIUM,
    "sound_heard": PRIORITY_HIGH,
    "entity_entered_zone": PRIORITY_LOW,
    "entity_left_zone": PRIORITY_IDLE,
}


class EventBus:
    """Manages WebSocket subscribers and broadcasts SimEvents to all of them."""

    def __init__(self) -> None:
        self._subscribers: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._event_history: list[dict[str, Any]] = []
        self._max_history = 200

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def recent_events(self) -> list[dict[str, Any]]:
        """Return the most recent events (newest first)."""
        return list(reversed(self._event_history))

    async def subscribe(self, ws: WebSocket) -> None:
        async with self._lock:
            self._subscribers.add(ws)
        logger.info("WebSocket subscriber added (total: %d)", len(self._subscribers))

    async def unsubscribe(self, ws: WebSocket) -> None:
        async with self._lock:
            self._subscribers.discard(ws)
        logger.info("WebSocket subscriber removed (total: %d)", len(self._subscribers))

    async def broadcast(self, event: SimEvent) -> None:
        """Send event to all subscribers. Remove any that fail."""
        payload = json.dumps(event.to_dict())

        # Store in history ring buffer
        self._event_history.append(event.to_dict())
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        dead: list[WebSocket] = []
        async with self._lock:
            subscribers = list(self._subscribers)

        for ws in subscribers:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._subscribers.discard(ws)
            logger.info("Removed %d dead WebSocket subscriber(s)", len(dead))
