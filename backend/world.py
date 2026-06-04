"""Spatial world model — 2D positions, zones, and entity tracking.

The world uses a flat 2D grid (x, z) matching Unity's XZ ground plane.
Coordinates are in meters (1 unit = 1 meter). The village spans roughly
-60 to +60 on both axes.

Each entity (NPC, player, object) has a position, facing angle, and zone.
The WorldState class provides spatial queries: radius search, zone lookup,
distance calculations, and FOV checks.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Zone Definitions ─────────────────────────────────────────────────────────
# Each zone is a named circular area in the village.
# x, z = center position; radius = boundary size.

ZONES: dict[str, dict[str, float]] = {
    "guard_post":   {"x": -30.0, "z": 30.0,  "radius": 10.0},
    "market_stall": {"x": 30.0,  "z": 30.0,  "radius": 12.0},
    "town_square":  {"x": 0.0,   "z": 0.0,   "radius": 15.0},
    "tavern":       {"x": -30.0, "z": -30.0, "radius": 10.0},
    "church":       {"x": 30.0,  "z": -30.0, "radius": 10.0},
    "smithy":       {"x": 0.0,   "z": -50.0, "radius": 8.0},
}


@dataclass
class WorldEntity:
    """A single entity in the 2D world."""

    id: str
    entity_type: str  # "npc", "player", "object"
    x: float = 0.0
    z: float = 0.0
    facing_angle: float = 0.0  # degrees, 0 = north (+Z), clockwise
    zone: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "x": round(self.x, 2),
            "z": round(self.z, 2),
            "facing_angle": round(self.facing_angle, 2),
            "zone": self.zone,
        }


class WorldState:
    """Manages all entities in the 2D simulation world.

    Provides spatial queries for vision/hearing systems:
    - Radius search (get all entities within range)
    - Zone lookup (get all entities in a named zone)
    - Distance calculation
    - FOV cone check (is target within NPC's field of view?)
    """

    def __init__(self) -> None:
        self._entities: dict[str, WorldEntity] = {}

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    def place_entity(
        self,
        entity_id: str,
        entity_type: str,
        x: float,
        z: float,
        facing_angle: float = 0.0,
        zone: Optional[str] = None,
    ) -> WorldEntity:
        """Add or update an entity in the world."""
        if zone is None:
            zone = self._detect_zone(x, z)

        entity = WorldEntity(
            id=entity_id,
            entity_type=entity_type,
            x=x,
            z=z,
            facing_angle=facing_angle,
            zone=zone,
        )
        self._entities[entity_id] = entity
        logger.debug("Placed entity %s at (%.1f, %.1f) zone=%s", entity_id, x, z, zone)
        return entity

    def move_entity(
        self,
        entity_id: str,
        x: float,
        z: float,
        facing_angle: Optional[float] = None,
        zone: Optional[str] = None,
    ) -> WorldEntity | None:
        """Update an entity's position. Returns None if entity not found."""
        entity = self._entities.get(entity_id)
        if entity is None:
            logger.warning("move_entity: entity %s not found", entity_id)
            return None

        old_zone = entity.zone
        entity.x = x
        entity.z = z
        if facing_angle is not None:
            entity.facing_angle = facing_angle
        entity.zone = zone if zone is not None else self._detect_zone(x, z)

        # Track zone changes
        if entity.zone != old_zone:
            logger.debug(
                "Entity %s moved from zone %s to %s",
                entity_id, old_zone, entity.zone,
            )

        return entity

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity from the world. Returns True if it existed."""
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    def get_entity(self, entity_id: str) -> WorldEntity | None:
        """Look up an entity by ID."""
        return self._entities.get(entity_id)

    def get_all_entities(self) -> list[WorldEntity]:
        """Return all entities."""
        return list(self._entities.values())

    def get_entities_by_type(self, entity_type: str) -> list[WorldEntity]:
        """Return all entities of a given type."""
        return [e for e in self._entities.values() if e.entity_type == entity_type]

    def get_entities_in_radius(
        self, x: float, z: float, radius: float, exclude_id: Optional[str] = None
    ) -> list[tuple[WorldEntity, float]]:
        """Return all entities within radius of (x, z), with distances.

        Returns list of (entity, distance) tuples sorted by distance.
        """
        results: list[tuple[WorldEntity, float]] = []
        for entity in self._entities.values():
            if entity.id == exclude_id:
                continue
            dist = self._distance_xy(x, z, entity.x, entity.z)
            if dist <= radius:
                results.append((entity, dist))
        results.sort(key=lambda t: t[1])
        return results

    def get_entities_in_zone(self, zone: str) -> list[WorldEntity]:
        """Return all entities currently in a named zone."""
        return [e for e in self._entities.values() if e.zone == zone]

    def distance(self, id1: str, id2: str) -> float | None:
        """Euclidean distance between two entities. Returns None if either not found."""
        e1 = self._entities.get(id1)
        e2 = self._entities.get(id2)
        if e1 is None or e2 is None:
            return None
        return self._distance_xy(e1.x, e1.z, e2.x, e2.z)

    def is_in_fov(
        self,
        observer_id: str,
        target_id: str,
        fov_degrees: float = 120.0,
        max_range: float = 20.0,
    ) -> tuple[bool, float]:
        """Check if target is within observer's field of view cone.

        Returns (is_visible, distance). Distance is always computed even if not visible.
        """
        observer = self._entities.get(observer_id)
        target = self._entities.get(target_id)
        if observer is None or target is None:
            return False, float("inf")

        dist = self._distance_xy(observer.x, observer.z, target.x, target.z)
        if dist > max_range or dist < 0.01:
            return False, dist

        # Direction from observer to target
        dx = target.x - observer.x
        dz = target.z - observer.z
        angle_to_target = math.degrees(math.atan2(dx, dz)) % 360

        # Observer's facing direction (already in degrees, 0=north, clockwise)
        facing = observer.facing_angle % 360

        # Angular difference (smallest angle between two directions)
        angle_diff = abs(angle_to_target - facing)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff

        half_fov = fov_degrees / 2.0
        return angle_diff <= half_fov, dist

    def get_snapshot(self) -> dict[str, Any]:
        """Full serialized world state for dashboard display."""
        return {
            "entity_count": self.entity_count,
            "entities": [e.to_dict() for e in self._entities.values()],
            "zones": {
                name: {**zone_data, "entities": [
                    e.id for e in self.get_entities_in_zone(name)
                ]}
                for name, zone_data in ZONES.items()
            },
        }

    def _detect_zone(self, x: float, z: float) -> Optional[str]:
        """Auto-detect which zone a position falls in, if any."""
        for zone_name, zone_data in ZONES.items():
            dist = self._distance_xy(x, z, zone_data["x"], zone_data["z"])
            if dist <= zone_data["radius"]:
                return zone_name
        return None

    @staticmethod
    def _distance_xy(x1: float, z1: float, x2: float, z2: float) -> float:
        """2D Euclidean distance."""
        return math.sqrt((x2 - x1) ** 2 + (z2 - z1) ** 2)
