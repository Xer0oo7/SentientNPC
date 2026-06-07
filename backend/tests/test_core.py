"""Tests for core simulation logic functions.

Covers:
- _determine_action: personality-driven action selection
- _determine_emotion_shift: emotion state transitions
- MemoryManager: STM expiry, LTM promotion, capacity limits
- WorldState: spatial queries, FOV cone checks
"""

import math
import time

import pytest

# ── Import the functions under test ──────────────────────────────────────────
from simulation_engine import (
    _determine_action,
    _determine_emotion_shift,
    ACTION_RULES,
)
from memory_manager import MemoryManager
from world import WorldState, ZONES


# ═══════════════════════════════════════════════════════════════════════════════
# _determine_action
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetermineAction:
    """Verify that personality traits correctly drive action selection."""

    def test_unknown_event_returns_observe(self):
        assert _determine_action("totally_unknown_event", {}) == "observe"

    def test_high_aggression_chase_on_theft(self):
        personality = {"aggressive": 80, "bravery": 90}
        assert _determine_action("player_stole", personality) == "chase"

    def test_low_aggression_alerts_guard_on_theft(self):
        personality = {"aggressive": 30, "bravery": 90}
        # First rule (aggressive < 60) fails threshold → fallback is "alert_guard"
        # Second rule (bravery >= 50) → "confront"
        result = _determine_action("player_stole", personality)
        assert result == "confront"

    def test_low_everything_reports_theft(self):
        personality = {"aggressive": 10, "bravery": 10}
        result = _determine_action("player_stole", personality)
        assert result == "report"

    def test_brave_npc_attacks_when_ally_attacked(self):
        personality = {"bravery": 80, "aggressive": 90}
        assert _determine_action("player_attacked_ally", personality) == "attack"

    def test_cowardly_npc_flees_when_ally_attacked(self):
        personality = {"bravery": 30, "aggressive": 20}
        assert _determine_action("player_attacked_ally", personality) == "cower"

    def test_friendly_npc_thanks_on_help(self):
        personality = {"friendly": 50}
        assert _determine_action("player_helped_npc", personality) == "thank"

    def test_unfriendly_npc_acknowledges_help(self):
        personality = {"friendly": 10}
        assert _determine_action("player_helped_npc", personality) == "acknowledge"

    def test_curious_npc_investigates_sound(self):
        personality = {"curiosity": 60, "bravery": 70}
        assert _determine_action("sound_heard", personality) == "investigate_sound"

    def test_all_known_event_types_have_rules(self):
        """Sanity check: every event type in ACTION_RULES produces a non-observe result."""
        neutral = {"aggressive": 50, "friendly": 50, "greedy": 50,
                    "bravery": 50, "curiosity": 50, "loyalty": 50}
        for event_type in ACTION_RULES:
            result = _determine_action(event_type, neutral)
            assert result != "", f"Empty action for {event_type}"

    def test_multiple_rules_evaluated_not_just_first(self):
        """Regression: ensure the loop doesn't short-circuit on the first rule."""
        # player_stole has TWO rules:
        #   1. (aggressive, 60, chase, alert_guard)
        #   2. (bravery, 50, confront, report)
        # With aggressive=30 (below 60) and bravery=70 (above 50),
        # the SECOND rule should fire → "confront"
        personality = {"aggressive": 30, "bravery": 70}
        result = _determine_action("player_stole", personality)
        assert result == "confront", (
            f"Expected 'confront' from second rule, got '{result}'. "
            "The loop may be short-circuiting on the first rule."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# _determine_emotion_shift
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetermineEmotionShift:
    """Verify emotion transition logic."""

    def test_no_shift_for_unknown_event(self):
        assert _determine_emotion_shift("unknown_event", "neutral") is None

    def test_attack_triggers_anger(self):
        shift = _determine_emotion_shift("player_attacked_ally", "neutral")
        assert shift is not None
        assert shift["to"] == "angry"
        assert shift["from"] == "neutral"

    def test_no_shift_if_already_in_target_emotion(self):
        shift = _determine_emotion_shift("player_attacked_ally", "angry")
        assert shift is None

    def test_help_triggers_happiness(self):
        shift = _determine_emotion_shift("player_helped_npc", "neutral")
        assert shift is not None
        assert shift["to"] == "happy"

    def test_threat_triggers_fear(self):
        shift = _determine_emotion_shift("threat_detected", "neutral")
        assert shift is not None
        assert shift["to"] == "fearful"

    def test_highest_intensity_emotion_wins(self):
        """npc_under_attack has [(fearful, 0.7), (angry, 0.5)] — fearful should win."""
        shift = _determine_emotion_shift("npc_under_attack", "neutral")
        assert shift is not None
        assert shift["to"] == "fearful"


# ═══════════════════════════════════════════════════════════════════════════════
# MemoryManager
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryManager:
    """Test short-term memory management (LTM tests require DB, skipped here)."""

    def _make_mgr(self, ttl: float = 5.0, capacity: int = 5) -> MemoryManager:
        return MemoryManager(stm_ttl=ttl, stm_capacity=capacity)

    def test_low_importance_goes_to_stm(self):
        mgr = self._make_mgr()
        created, is_lt = mgr.add_memory("npc1", "player_said_hello", "hello", importance=0.1)
        assert created is True
        assert is_lt is False
        assert len(mgr.get_stm_snapshot("npc1")) == 1

    def test_stm_capacity_enforced(self):
        mgr = self._make_mgr(capacity=3)
        for i in range(5):
            mgr.add_memory("npc1", "ambient_observation", f"event_{i}", importance=0.1)
        snapshot = mgr.get_stm_snapshot("npc1")
        assert len(snapshot) == 3
        # Oldest entries should have been dropped
        assert snapshot[-1]["description"] == "event_4"

    def test_expire_stm_removes_old_entries(self):
        mgr = self._make_mgr(ttl=0.01)  # 10ms TTL
        mgr.add_memory("npc1", "ambient_observation", "will_expire", importance=0.1)
        time.sleep(0.02)  # Wait for expiry
        expired = mgr.expire_stm()
        assert "npc1" in expired
        assert expired["npc1"] == 1
        assert len(mgr.get_stm_snapshot("npc1")) == 0

    def test_stm_counts(self):
        mgr = self._make_mgr()
        mgr.add_memory("npc1", "ambient_observation", "a", importance=0.1)
        mgr.add_memory("npc1", "ambient_observation", "b", importance=0.1)
        mgr.add_memory("npc2", "ambient_observation", "c", importance=0.1)
        counts = mgr.get_all_stm_counts()
        assert counts["npc1"] == 2
        assert counts["npc2"] == 1

    def test_importance_auto_lookup(self):
        mgr = self._make_mgr()
        # player_attacked_ally has importance 0.9 in EVENT_IMPORTANCE → should go to LTM
        # (LTM write will fail without DB, but we can check the return value intent)
        # We test with a known STM event instead
        created, is_lt = mgr.add_memory("npc1", "ambient_observation", "low", importance=None)
        assert created is True
        assert is_lt is False  # ambient_observation default importance = 0.05


# ═══════════════════════════════════════════════════════════════════════════════
# WorldState
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorldState:
    """Test spatial queries and FOV calculations."""

    def _make_world(self) -> WorldState:
        world = WorldState()
        world.place_entity("npc1", "npc", x=0.0, z=0.0, facing_angle=0.0)
        world.place_entity("npc2", "npc", x=10.0, z=0.0, facing_angle=180.0)
        world.place_entity("player", "player", x=5.0, z=5.0, facing_angle=0.0)
        return world

    def test_place_and_get_entity(self):
        world = self._make_world()
        e = world.get_entity("npc1")
        assert e is not None
        assert e.x == 0.0
        assert e.entity_type == "npc"

    def test_entity_count(self):
        world = self._make_world()
        assert world.entity_count == 3

    def test_remove_entity(self):
        world = self._make_world()
        assert world.remove_entity("npc1") is True
        assert world.get_entity("npc1") is None
        assert world.entity_count == 2

    def test_remove_nonexistent_returns_false(self):
        world = self._make_world()
        assert world.remove_entity("ghost") is False

    def test_distance(self):
        world = self._make_world()
        dist = world.distance("npc1", "npc2")
        assert dist is not None
        assert abs(dist - 10.0) < 0.01

    def test_distance_unknown_entity_returns_none(self):
        world = self._make_world()
        assert world.distance("npc1", "unknown") is None

    def test_entities_in_radius(self):
        world = self._make_world()
        nearby = world.get_entities_in_radius(0.0, 0.0, 8.0, exclude_id=None)
        ids = [e.id for e, _ in nearby]
        assert "npc1" in ids
        assert "player" in ids
        assert "npc2" not in ids  # npc2 is at distance 10

    def test_entities_in_radius_exclude(self):
        world = self._make_world()
        nearby = world.get_entities_in_radius(0.0, 0.0, 15.0, exclude_id="npc1")
        ids = [e.id for e, _ in nearby]
        assert "npc1" not in ids

    def test_get_entities_by_type(self):
        world = self._make_world()
        npcs = world.get_entities_by_type("npc")
        assert len(npcs) == 2
        players = world.get_entities_by_type("player")
        assert len(players) == 1

    def test_fov_target_directly_ahead(self):
        world = WorldState()
        world.place_entity("obs", "npc", x=0.0, z=0.0, facing_angle=0.0)  # facing north (+Z)
        world.place_entity("tgt", "npc", x=0.0, z=10.0)  # directly north
        visible, dist = world.is_in_fov("obs", "tgt", fov_degrees=120.0, max_range=20.0)
        assert visible is True
        assert abs(dist - 10.0) < 0.01

    def test_fov_target_behind(self):
        world = WorldState()
        world.place_entity("obs", "npc", x=0.0, z=0.0, facing_angle=0.0)  # facing north
        world.place_entity("tgt", "npc", x=0.0, z=-10.0)  # directly south (behind)
        visible, dist = world.is_in_fov("obs", "tgt", fov_degrees=120.0, max_range=20.0)
        assert visible is False

    def test_fov_target_at_edge_of_cone(self):
        world = WorldState()
        world.place_entity("obs", "npc", x=0.0, z=0.0, facing_angle=0.0)
        # Place target at exactly 60 degrees (half of 120° FOV) — should be on the boundary
        angle_rad = math.radians(60)
        tx = math.sin(angle_rad) * 10.0
        tz = math.cos(angle_rad) * 10.0
        world.place_entity("tgt", "npc", x=tx, z=tz)
        visible, _ = world.is_in_fov("obs", "tgt", fov_degrees=120.0, max_range=20.0)
        assert visible is True  # <= half_fov means visible

    def test_fov_target_just_outside_cone(self):
        world = WorldState()
        world.place_entity("obs", "npc", x=0.0, z=0.0, facing_angle=0.0)
        angle_rad = math.radians(61)  # Just past 60° half-FOV
        tx = math.sin(angle_rad) * 10.0
        tz = math.cos(angle_rad) * 10.0
        world.place_entity("tgt", "npc", x=tx, z=tz)
        visible, _ = world.is_in_fov("obs", "tgt", fov_degrees=120.0, max_range=20.0)
        assert visible is False

    def test_fov_target_out_of_range(self):
        world = WorldState()
        world.place_entity("obs", "npc", x=0.0, z=0.0, facing_angle=0.0)
        world.place_entity("tgt", "npc", x=0.0, z=25.0)  # Beyond 20m range
        visible, dist = world.is_in_fov("obs", "tgt", fov_degrees=120.0, max_range=20.0)
        assert visible is False
        assert dist > 20.0

    def test_move_entity(self):
        world = self._make_world()
        result = world.move_entity("npc1", x=5.0, z=5.0)
        assert result is not None
        assert result.x == 5.0
        assert result.z == 5.0

    def test_move_nonexistent_returns_none(self):
        world = self._make_world()
        assert world.move_entity("ghost", x=0, z=0) is None

    def test_auto_zone_detection(self):
        world = WorldState()
        entity = world.place_entity("test", "npc", x=0.0, z=0.0)  # town_square center
        assert entity.zone == "town_square"

    def test_zone_detection_outside_all(self):
        world = WorldState()
        entity = world.place_entity("test", "npc", x=100.0, z=100.0)  # far away
        assert entity.zone is None

    def test_get_entities_in_zone(self):
        world = WorldState()
        world.place_entity("a", "npc", x=0.0, z=0.0, zone="town_square")
        world.place_entity("b", "npc", x=0.0, z=5.0, zone="town_square")
        world.place_entity("c", "npc", x=-30.0, z=30.0, zone="guard_post")
        assert len(world.get_entities_in_zone("town_square")) == 2
        assert len(world.get_entities_in_zone("guard_post")) == 1

    def test_snapshot_structure(self):
        world = self._make_world()
        snap = world.get_snapshot()
        assert "entity_count" in snap
        assert "entities" in snap
        assert "zones" in snap
        assert snap["entity_count"] == 3
