"""NPC Perception Engine — vision cone scanning and hearing propagation.

The PerceptionEngine runs as part of the simulation tick loop:
  - Vision: Each tick, every NPC scans for entities within their FOV cone.
    Detected targets generate 'vision_spotted' events in the NPC's queue.
    A cooldown prevents spamming the same target detection.
  - Hearing: Event-triggered. When a sound-producing event fires, all NPCs
    within hearing range receive 'sound_heard' events with intensity based
    on distance falloff.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

from world import WorldState

if TYPE_CHECKING:
    from simulation_engine import SimulationEngine

logger = logging.getLogger(__name__)


# ── Sound Event Configuration ────────────────────────────────────────────────
# Which simulation event types produce detectable sounds?
# loudness: 0.0–1.0 base volume; sound_type: category label.

SOUND_EVENTS: dict[str, dict[str, Any]] = {
    "player_attacked_ally": {"loudness": 1.0, "sound_type": "combat"},
    "npc_under_attack":     {"loudness": 0.9, "sound_type": "combat"},
    "player_stole":         {"loudness": 0.3, "sound_type": "stealth"},
    "sound_loud":           {"loudness": 1.0, "sound_type": "explosion"},
    "player_said_hello":    {"loudness": 0.2, "sound_type": "speech"},
    "give_gift":            {"loudness": 0.1, "sound_type": "ambient"},
    "player_completed_quest": {"loudness": 0.4, "sound_type": "speech"},
    "player_helped_npc":    {"loudness": 0.3, "sound_type": "speech"},
    "threat_detected":      {"loudness": 0.7, "sound_type": "alert"},
}

# Default perception parameters
DEFAULT_VISION_RANGE = 20.0   # meters
DEFAULT_VISION_FOV = 120.0    # degrees
DEFAULT_HEARING_RANGE = 30.0  # meters
VISION_COOLDOWN_TICKS = 5     # min ticks between re-detecting same target


class PerceptionEngine:
    """Handles vision scanning and hearing propagation for all NPCs."""

    def __init__(self, world: WorldState) -> None:
        self.world = world
        self._sim_engine: Optional[SimulationEngine] = None

        # Vision cooldown tracking: {npc_id: {target_id: last_detection_tick}}
        self._vision_cooldowns: dict[str, dict[str, int]] = {}

        # Per-NPC perception config overrides: {npc_id: {vision_range, vision_fov, hearing_range}}
        self._perception_configs: dict[str, dict[str, float]] = {}

        # Recent perception events for dashboard display
        self._recent_perception_events: list[dict[str, Any]] = []
        self._max_perception_history = 100

    def set_sim_engine(self, engine: SimulationEngine) -> None:
        """Set reference to simulation engine (called after both are created)."""
        self._sim_engine = engine

    def set_perception_config(
        self,
        npc_id: str,
        vision_range: Optional[float] = None,
        vision_fov: Optional[float] = None,
        hearing_range: Optional[float] = None,
    ) -> dict[str, float]:
        """Update perception config for an NPC. Returns the full config."""
        config = self._perception_configs.get(npc_id, {
            "vision_range": DEFAULT_VISION_RANGE,
            "vision_fov": DEFAULT_VISION_FOV,
            "hearing_range": DEFAULT_HEARING_RANGE,
        })
        if vision_range is not None:
            config["vision_range"] = vision_range
        if vision_fov is not None:
            config["vision_fov"] = vision_fov
        if hearing_range is not None:
            config["hearing_range"] = hearing_range
        self._perception_configs[npc_id] = config
        return config

    def get_perception_config(self, npc_id: str) -> dict[str, float]:
        """Get perception config for an NPC (returns defaults if not set)."""
        return self._perception_configs.get(npc_id, {
            "vision_range": DEFAULT_VISION_RANGE,
            "vision_fov": DEFAULT_VISION_FOV,
            "hearing_range": DEFAULT_HEARING_RANGE,
        })

    def tick_perception(self, current_tick: int) -> list[dict[str, Any]]:
        """Run vision scans for all NPCs. Called once per simulation tick.

        Returns a list of perception events generated this tick.
        """
        events_generated: list[dict[str, Any]] = []

        npc_entities = self.world.get_entities_by_type("npc")

        for npc_entity in npc_entities:
            npc_id = npc_entity.id
            config = self.get_perception_config(npc_id)
            vision_range = config["vision_range"]
            vision_fov = config["vision_fov"]

            # Get all entities in vision range
            nearby = self.world.get_entities_in_radius(
                npc_entity.x, npc_entity.z, vision_range, exclude_id=npc_id
            )

            for target_entity, distance in nearby:
                # Check FOV cone
                is_visible, dist = self.world.is_in_fov(
                    npc_id, target_entity.id, vision_fov, vision_range
                )

                if not is_visible:
                    continue

                # Check cooldown
                if self._is_on_cooldown(npc_id, target_entity.id, current_tick):
                    continue

                # Record detection
                self._set_cooldown(npc_id, target_entity.id, current_tick)

                # Generate vision_spotted event
                event_data = {
                    "perception_type": "vision",
                    "npc_id": npc_id,
                    "target_id": target_entity.id,
                    "target_type": target_entity.entity_type,
                    "distance": round(dist, 2),
                    "target_zone": target_entity.zone,
                    "tick": current_tick,
                }
                events_generated.append(event_data)
                self._record_perception_event(event_data)

                # Enqueue into simulation engine
                if self._sim_engine is not None:
                    description = (
                        f"{npc_id} spotted {target_entity.id} "
                        f"({target_entity.entity_type}) at distance {dist:.1f}m"
                    )
                    self._sim_engine.enqueue_event(
                        npc_id=npc_id,
                        event_type="vision_spotted",
                        description=description,
                        location=npc_entity.zone,
                    )

        return events_generated

    def propagate_sound(
        self,
        source_id: str,
        event_type: str,
        current_tick: int,
        source_x: Optional[float] = None,
        source_z: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        """Propagate a sound from a source to all NPCs within hearing range.

        If source_x/source_z not provided, uses the source entity's position.
        Returns list of hearing events generated.
        """
        sound_config = SOUND_EVENTS.get(event_type)
        if sound_config is None:
            return []

        # Determine sound origin position
        if source_x is not None and source_z is not None:
            sx, sz = source_x, source_z
        else:
            source_entity = self.world.get_entity(source_id)
            if source_entity is None:
                logger.warning("propagate_sound: source %s not found", source_id)
                return []
            sx, sz = source_entity.x, source_entity.z

        loudness = sound_config["loudness"]
        sound_type = sound_config["sound_type"]

        events_generated: list[dict[str, Any]] = []
        npc_entities = self.world.get_entities_by_type("npc")

        for npc_entity in npc_entities:
            # Don't send sound event to the source NPC itself
            if npc_entity.id == source_id:
                continue

            config = self.get_perception_config(npc_entity.id)
            hearing_range = config["hearing_range"]

            # Calculate distance and intensity
            dist = self.world._distance_xy(sx, sz, npc_entity.x, npc_entity.z)
            if dist > hearing_range:
                continue

            # Intensity falloff: louder sounds carry further effectively
            intensity = loudness * max(0.0, 1.0 - (dist / hearing_range))
            if intensity < 0.05:
                continue  # Too faint to notice

            event_data = {
                "perception_type": "hearing",
                "npc_id": npc_entity.id,
                "source_id": source_id,
                "sound_type": sound_type,
                "event_type": event_type,
                "distance": round(dist, 2),
                "intensity": round(intensity, 3),
                "tick": current_tick,
            }
            events_generated.append(event_data)
            self._record_perception_event(event_data)

            # Enqueue into simulation engine
            if self._sim_engine is not None:
                description = (
                    f"{npc_entity.id} heard {sound_type} sound from "
                    f"{source_id} ({event_type}) at distance {dist:.1f}m "
                    f"(intensity {intensity:.2f})"
                )
                self._sim_engine.enqueue_event(
                    npc_id=npc_entity.id,
                    event_type="sound_heard",
                    description=description,
                    location=npc_entity.zone,
                    importance=min(0.9, intensity),  # Cap importance at 0.9
                )

        return events_generated

    def get_npc_fov_data(self, npc_id: str) -> dict[str, Any] | None:
        """Return FOV visualization data for an NPC (for dashboard rendering)."""
        entity = self.world.get_entity(npc_id)
        if entity is None or entity.entity_type != "npc":
            return None

        config = self.get_perception_config(npc_id)
        return {
            "npc_id": npc_id,
            "x": entity.x,
            "z": entity.z,
            "facing_angle": entity.facing_angle,
            "vision_range": config["vision_range"],
            "vision_fov": config["vision_fov"],
            "hearing_range": config["hearing_range"],
        }

    def get_nearby_entities(self, npc_id: str) -> dict[str, Any] | None:
        """Return all entities near an NPC with visibility status."""
        entity = self.world.get_entity(npc_id)
        if entity is None:
            return None

        config = self.get_perception_config(npc_id)
        max_range = max(config["vision_range"], config["hearing_range"])
        nearby = self.world.get_entities_in_radius(
            entity.x, entity.z, max_range, exclude_id=npc_id
        )

        results = []
        for target, dist in nearby:
            is_visible, _ = self.world.is_in_fov(
                npc_id, target.id, config["vision_fov"], config["vision_range"]
            )
            in_hearing = dist <= config["hearing_range"]
            results.append({
                "id": target.id,
                "entity_type": target.entity_type,
                "distance": round(dist, 2),
                "in_vision": is_visible,
                "in_hearing": in_hearing,
                "zone": target.zone,
            })

        return {
            "npc_id": npc_id,
            "position": {"x": entity.x, "z": entity.z},
            "nearby": results,
        }

    def get_recent_perception_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent perception events (newest first)."""
        return list(reversed(self._recent_perception_events[-limit:]))

    def _is_on_cooldown(self, npc_id: str, target_id: str, current_tick: int) -> bool:
        """Check if vision detection is on cooldown for this NPC-target pair."""
        npc_cooldowns = self._vision_cooldowns.get(npc_id, {})
        last_tick = npc_cooldowns.get(target_id)
        if last_tick is None:
            return False
        return (current_tick - last_tick) < VISION_COOLDOWN_TICKS

    def _set_cooldown(self, npc_id: str, target_id: str, current_tick: int) -> None:
        """Record vision detection tick for cooldown tracking."""
        if npc_id not in self._vision_cooldowns:
            self._vision_cooldowns[npc_id] = {}
        self._vision_cooldowns[npc_id][target_id] = current_tick

    def _record_perception_event(self, event: dict[str, Any]) -> None:
        """Store perception event in ring buffer for dashboard display."""
        self._recent_perception_events.append(event)
        if len(self._recent_perception_events) > self._max_perception_history:
            self._recent_perception_events = self._recent_perception_events[
                -self._max_perception_history:
            ]
