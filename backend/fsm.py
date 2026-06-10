"""Finite state machine helpers for persistent NPC decision state.

The first AI implementation phase keeps state simple and explicit:
- NPCs persist a high-level state in the database
- State changes only happen through deterministic event rules
- The simulation engine can use the current state as a fallback signal
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


FSM_STATES: tuple[str, ...] = (
    "idle",
    "patrol",
    "investigate",
    "talk",
    "trade",
    "chase",
    "flee",
    "sleep",
)


STATE_DEFAULT_ACTIONS: dict[str, str] = {
    "idle": "observe",
    "patrol": "patrol_area",
    "investigate": "search_area",
    "talk": "engage_conversation",
    "trade": "barter",
    "chase": "pursue_target",
    "flee": "retreat",
    "sleep": "sleep",
}


@dataclass(frozen=True)
class FSMTransition:
    previous_state: str
    next_state: str
    event_type: str
    reason: str


def normalize_state(value: Optional[str]) -> str:
    if value in FSM_STATES:
        return value
    return "idle"


def derive_initial_state(zone: Optional[str], emotion: Optional[str] = None) -> str:
    """Pick a sensible starting state for seeded or newly created NPCs."""
    if emotion == "fearful":
        return "flee"
    if emotion == "sad":
        return "sleep"

    zone_defaults = {
        "guard_post": "patrol",
        "market_stall": "trade",
        "smithy": "patrol",
        "town_square": "talk",
        "tavern": "talk",
        "church": "talk",
    }
    return zone_defaults.get(zone, "idle")


def transition_state(
    current_state: Optional[str],
    event_type: str,
    personality: dict[str, float],
    emotion: Optional[str] = None,
) -> FSMTransition:
    """Return the next FSM state using explicit event rules.

    The rules are intentionally conservative so the NPC keeps its state until a
    strong stimulus justifies a transition.
    """

    state = normalize_state(current_state)
    aggressive = personality.get("aggressive", 50)
    friendly = personality.get("friendly", 50)
    bravery = personality.get("bravery", 50)
    curiosity = personality.get("curiosity", 50)

    if event_type in {"player_attacked_ally", "npc_under_attack"}:
        if bravery >= 70:
            next_state = "chase"
            reason = "high bravery response to direct attack"
        else:
            next_state = "flee"
            reason = "low bravery response to direct attack"
    elif event_type == "player_stole":
        if aggressive >= 60 or bravery >= 55:
            next_state = "chase"
            reason = "theft escalated into pursuit"
        else:
            next_state = "investigate"
            reason = "theft triggered investigation"
    elif event_type in {"threat_detected", "sound_loud", "sound_heard", "vision_spotted"}:
        if curiosity >= 55 or bravery >= 60:
            next_state = "investigate"
            reason = "curiosity or bravery triggered investigation"
        elif emotion == "fearful" or bravery < 35:
            next_state = "flee"
            reason = "fearful response to a perceived threat"
        else:
            next_state = "patrol"
            reason = "maintaining cautious patrol"
    elif event_type in {"player_helped_npc", "player_completed_quest", "give_gift", "player_said_hello"}:
        if friendly >= 40:
            next_state = "talk"
            reason = "social interaction reinforced conversation"
        else:
            next_state = "idle"
            reason = "social interaction did not change routine"
    elif event_type == "npc_idle_thought":
        next_state = "idle"
        reason = "background thought keeps the NPC idle"
    elif event_type == "schedule_check":
        next_state = state
        reason = "schedule check preserves the current routine"
    else:
        next_state = state
        reason = "no FSM rule matched, state preserved"

    return FSMTransition(previous_state=state, next_state=normalize_state(next_state), event_type=event_type, reason=reason)


def resolve_state_action(state: Optional[str], fallback_action: str = "observe") -> str:
    """Choose a state-driven fallback action when the event rules are generic."""
    return STATE_DEFAULT_ACTIONS.get(normalize_state(state), fallback_action)
