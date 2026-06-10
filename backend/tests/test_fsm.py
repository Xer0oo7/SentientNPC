"""Tests for the first-phase NPC FSM helpers."""

from fsm import derive_initial_state, normalize_state, resolve_state_action, transition_state


def test_normalize_state_falls_back_to_idle():
    assert normalize_state("not-a-state") == "idle"


def test_initial_state_uses_zone_defaults():
    assert derive_initial_state("guard_post", "neutral") == "patrol"
    assert derive_initial_state("market_stall", "neutral") == "trade"
    assert derive_initial_state("tavern", "neutral") == "talk"


def test_initial_state_uses_emotion_override():
    assert derive_initial_state("town_square", "fearful") == "flee"
    assert derive_initial_state("town_square", "sad") == "sleep"


def test_theft_transitions_aggressive_npc_to_chase():
    transition = transition_state("idle", "player_stole", {"aggressive": 80, "bravery": 65})
    assert transition.previous_state == "idle"
    assert transition.next_state == "chase"
    assert "pursuit" in transition.reason or "theft" in transition.reason


def test_direct_attack_transitions_cautious_npc_to_flee():
    transition = transition_state("patrol", "npc_under_attack", {"bravery": 20}, emotion="neutral")
    assert transition.next_state == "flee"


def test_social_events_promote_talk_state_for_friendly_npcs():
    transition = transition_state("idle", "player_said_hello", {"friendly": 70})
    assert transition.next_state == "talk"


def test_unknown_events_preserve_current_state():
    transition = transition_state("investigate", "completely_unknown", {})
    assert transition.next_state == "investigate"


def test_state_actions_provide_fallbacks():
    assert resolve_state_action("chase") == "pursue_target"
    assert resolve_state_action("trade") == "barter"
    assert resolve_state_action("not-a-state") == "observe"
