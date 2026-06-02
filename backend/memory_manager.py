"""NPC Memory Manager — short-term cache with TTL + long-term SQLite persistence.

Short-term memories (STM) live in an in-memory dict, keyed by npc_id.
Each STM entry has a created_at timestamp and expires after `stm_ttl` seconds.
When importance >= 0.7, memories are immediately promoted to long-term (SQLite).
The tick engine calls `expire_stm()` each tick to garbage-collect expired entries.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from database import Memory, SessionLocal
from event_bus import EVENT_IMPORTANCE

logger = logging.getLogger(__name__)


@dataclass
class STMEntry:
    """A single short-term memory entry held in-memory."""

    npc_id: str
    event_type: str
    description: str
    location: Optional[str]
    importance: float
    created_at: float = field(default_factory=time.time)

    def is_expired(self, ttl: float) -> bool:
        return (time.time() - self.created_at) > ttl

    def age_seconds(self) -> float:
        return time.time() - self.created_at


class MemoryManager:
    """Manages short-term and long-term memory for all NPCs.

    - STM: in-memory dict of lists, TTL-based expiry
    - LTM: SQLite via the existing Memory ORM model
    """

    def __init__(self, stm_ttl: float = 30.0, stm_capacity: int = 20) -> None:
        self.stm_ttl = stm_ttl
        self.stm_capacity = stm_capacity
        self._stm: dict[str, list[STMEntry]] = {}  # npc_id -> entries

    def add_memory(
        self,
        npc_id: str,
        event_type: str,
        description: str,
        location: Optional[str] = None,
        importance: Optional[float] = None,
    ) -> tuple[bool, bool]:
        """Add a memory event for an NPC.

        Returns (memory_created, is_longterm).
        - importance is auto-looked-up from EVENT_IMPORTANCE if not provided.
        - If importance >= 0.7, written directly to SQLite as long-term.
        - Otherwise, stored in STM cache with TTL expiry.
        """
        if importance is None:
            importance = EVENT_IMPORTANCE.get(event_type, 0.3)

        is_longterm = importance >= 0.7

        if is_longterm:
            self._write_longterm(npc_id, event_type, description, location, importance)
            return True, True

        # Add to short-term memory
        if npc_id not in self._stm:
            self._stm[npc_id] = []

        entry = STMEntry(
            npc_id=npc_id,
            event_type=event_type,
            description=description,
            location=location,
            importance=importance,
        )
        self._stm[npc_id].append(entry)

        # Enforce capacity — drop oldest if over limit
        if len(self._stm[npc_id]) > self.stm_capacity:
            self._stm[npc_id] = self._stm[npc_id][-self.stm_capacity:]

        return True, False

    def expire_stm(self) -> dict[str, int]:
        """Remove expired STM entries for all NPCs. Returns {npc_id: expired_count}."""
        expired_counts: dict[str, int] = {}
        for npc_id in list(self._stm.keys()):
            before = len(self._stm[npc_id])
            self._stm[npc_id] = [
                e for e in self._stm[npc_id] if not e.is_expired(self.stm_ttl)
            ]
            after = len(self._stm[npc_id])
            diff = before - after
            if diff > 0:
                expired_counts[npc_id] = diff
            if not self._stm[npc_id]:
                del self._stm[npc_id]
        return expired_counts

    def get_stm_snapshot(self, npc_id: str) -> list[dict]:
        """Return current STM entries for an NPC (for dashboard display)."""
        entries = self._stm.get(npc_id, [])
        return [
            {
                "npc_id": e.npc_id,
                "event_type": e.event_type,
                "description": e.description,
                "location": e.location,
                "importance": e.importance,
                "age_seconds": round(e.age_seconds(), 1),
                "is_longterm": False,
            }
            for e in entries
        ]

    def get_all_stm_counts(self) -> dict[str, int]:
        """Return {npc_id: stm_count} for all NPCs with active STM."""
        return {npc_id: len(entries) for npc_id, entries in self._stm.items()}

    def query_recent(
        self,
        npc_id: str,
        event_type: Optional[str] = None,
        min_importance: Optional[float] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Query both STM and LTM for an NPC's recent memories."""
        results: list[dict] = []

        # STM entries (newest first)
        stm_entries = list(reversed(self._stm.get(npc_id, [])))
        for e in stm_entries:
            if event_type and e.event_type != event_type:
                continue
            if min_importance is not None and e.importance < min_importance:
                continue
            results.append(
                {
                    "event_type": e.event_type,
                    "description": e.description,
                    "importance": e.importance,
                    "is_longterm": False,
                    "age_seconds": round(e.age_seconds(), 1),
                }
            )

        # LTM entries from SQLite
        db = SessionLocal()
        try:
            query = db.query(Memory).filter(Memory.npc_id == npc_id)
            if event_type:
                query = query.filter(Memory.event_type == event_type)
            if min_importance is not None:
                query = query.filter(Memory.importance >= min_importance)
            ltm_rows = (
                query.order_by(Memory.timestamp.desc()).limit(limit).all()
            )
            for row in ltm_rows:
                results.append(
                    {
                        "event_type": row.event_type,
                        "description": row.description,
                        "importance": row.importance,
                        "is_longterm": True,
                        "age_seconds": None,
                    }
                )
        finally:
            db.close()

        return results[:limit]

    @staticmethod
    def _write_longterm(
        npc_id: str,
        event_type: str,
        description: str,
        location: Optional[str],
        importance: float,
    ) -> None:
        """Persist a memory directly to SQLite long-term storage."""
        db = SessionLocal()
        try:
            memory = Memory(
                npc_id=npc_id,
                event_type=event_type,
                description=description,
                location=location,
                importance=importance,
                is_longterm=True,
            )
            db.add(memory)
            db.commit()
            logger.debug("LTM written: npc=%s type=%s imp=%.2f", npc_id, event_type, importance)
        except Exception:
            db.rollback()
            logger.exception("Failed to write long-term memory for %s", npc_id)
        finally:
            db.close()
