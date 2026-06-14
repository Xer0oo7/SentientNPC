"""Tests for behavior tree decision selection."""

from behaviour_tree import DecisionOutcome, evaluate_tree, event_tree
from decision_context import DecisionContext
from simulation_engine import _determine_action


def make_context(**overrides):
    base = {
        "npc_id": "npc_1",
        "event_type": "player_stole",
        "description": "a theft happened",
        "priority": 1,
        "importance": 0.8,
        "location": "market",
        "personality": {"aggressive": 30, "bravery": 70, "friendly": 20, "curiosity": 20, "greedy": 10},
        "emotion": "neutral",
        "fsm_state": "patrol",
        "reputation": 0.0,
        "relationship_score": 0.0,
        "current_zone": "market_stall",
        "position": (0.0, 0.0),
        "recent_memories": [],
        "nearby_entities": [],
    }
    base.update(overrides)
    return DecisionContext(**base)


def test_player_stole_uses_second_bt_branch():
    context = make_context(personality={"aggressive": 30, "bravery": 70})
    outcome = evaluate_tree("player_stole", context)

    assert outcome.success is True
    assert outcome.action == "confront"
    assert any(step["node_type"] == "condition" and step["node"] == "aggressive_at_least_60" for step in outcome.trace)
    assert any(step["node_type"] == "selector" and step["status"] == "selected" for step in outcome.trace)


def test_sound_heard_falls_back_to_brave_branch():
    context = make_context(
        event_type="sound_heard",
        personality={"curiosity": 20, "bravery": 80},
    )
    outcome = evaluate_tree("sound_heard", context)

    assert outcome.success is True
    assert outcome.action == "move_toward_sound"


def test_unknown_event_defaults_to_observe():
    context = make_context(event_type="mysterious_event")
    outcome = evaluate_tree("mysterious_event", context)

    assert outcome.success is True
    assert outcome.action == "observe"


def test_determine_action_prefers_bt_when_context_is_present():
    context = make_context(personality={"aggressive": 30, "bravery": 70})

    assert _determine_action("player_stole", context.personality, context=context) == "confront"
