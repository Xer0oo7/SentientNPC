"""Behavior tree primitives for NPC decision selection.

The tree keeps the current migration slice intentionally small:
- `Condition` nodes gate branches with explicit predicates
- `Action` nodes terminate a successful branch with the chosen action
- `Sequence` and `Selector` compose those pieces into readable decision paths

Each evaluation returns a trace so the simulation engine can log which
conditions passed and which branch produced the final action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class DecisionOutcome:
    """Result of a behavior tree evaluation."""

    success: bool
    action: Optional[str] = None
    reason: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)
    winning_node: Optional[str] = None


class Node:
    """Base behavior tree node."""

    def __init__(self, name: str) -> None:
        self.name = name

    def evaluate(self, context: Any) -> DecisionOutcome:
        raise NotImplementedError


class Condition(Node):
    """Gate a branch with a boolean predicate."""

    def __init__(self, name: str, predicate: Callable[[Any], bool], detail: str) -> None:
        super().__init__(name)
        self._predicate = predicate
        self.detail = detail

    def evaluate(self, context: Any) -> DecisionOutcome:
        passed = bool(self._predicate(context))
        detail = self.detail if passed else f"{self.detail} (failed)"
        return DecisionOutcome(
            success=passed,
            reason=detail,
            trace=[
                {
                    "node_type": "condition",
                    "node": self.name,
                    "passed": passed,
                    "detail": self.detail,
                }
            ],
            winning_node=self.name if passed else None,
        )


class Action(Node):
    """Return a selected action and end the branch successfully."""

    def __init__(self, name: str, action_name: str, detail: Optional[str] = None) -> None:
        super().__init__(name)
        self.action_name = action_name
        self.detail = detail or action_name

    def evaluate(self, context: Any) -> DecisionOutcome:
        return DecisionOutcome(
            success=True,
            action=self.action_name,
            reason=self.detail,
            trace=[
                {
                    "node_type": "action",
                    "node": self.name,
                    "action": self.action_name,
                    "detail": self.detail,
                }
            ],
            winning_node=self.name,
        )


class Sequence(Node):
    """Evaluate children in order until one fails."""

    def __init__(self, name: str, children: list[Node]) -> None:
        super().__init__(name)
        self.children = children

    def evaluate(self, context: Any) -> DecisionOutcome:
        trace: list[dict[str, Any]] = [
            {"node_type": "sequence", "node": self.name, "status": "start"}
        ]
        last_action: Optional[str] = None
        last_reason = ""
        last_winning_node: Optional[str] = None

        for child in self.children:
            outcome = child.evaluate(context)
            trace.extend(outcome.trace)
            if not outcome.success:
                trace.append(
                    {
                        "node_type": "sequence",
                        "node": self.name,
                        "status": "failed",
                        "reason": outcome.reason,
                    }
                )
                return DecisionOutcome(
                    success=False,
                    reason=outcome.reason,
                    trace=trace,
                    winning_node=outcome.winning_node,
                )
            if outcome.action is not None:
                last_action = outcome.action
            last_reason = outcome.reason or last_reason
            last_winning_node = outcome.winning_node or last_winning_node

        trace.append(
            {
                "node_type": "sequence",
                "node": self.name,
                "status": "passed",
                "action": last_action,
                "reason": last_reason,
            }
        )
        return DecisionOutcome(
            success=True,
            action=last_action,
            reason=last_reason,
            trace=trace,
            winning_node=last_winning_node or self.name,
        )


class Selector(Node):
    """Evaluate children until one succeeds."""

    def __init__(self, name: str, children: list[Node]) -> None:
        super().__init__(name)
        self.children = children

    def evaluate(self, context: Any) -> DecisionOutcome:
        trace: list[dict[str, Any]] = [
            {"node_type": "selector", "node": self.name, "status": "start"}
        ]

        for child in self.children:
            outcome = child.evaluate(context)
            trace.extend(outcome.trace)
            if outcome.success:
                trace.append(
                    {
                        "node_type": "selector",
                        "node": self.name,
                        "status": "selected",
                        "selected_node": outcome.winning_node or child.name,
                        "action": outcome.action,
                        "reason": outcome.reason,
                    }
                )
                return DecisionOutcome(
                    success=True,
                    action=outcome.action,
                    reason=outcome.reason,
                    trace=trace,
                    winning_node=outcome.winning_node or child.name,
                )

        trace.append(
            {
                "node_type": "selector",
                "node": self.name,
                "status": "failed",
                "reason": "no branch matched",
            }
        )
        return DecisionOutcome(success=False, reason="no branch matched", trace=trace, winning_node=self.name)


def trait_at_least(trait: str, threshold: float) -> Condition:
    """Create a trait-threshold predicate condition."""

    return Condition(
        name=f"{trait}_at_least_{threshold:g}",
        predicate=lambda context, trait=trait, threshold=threshold: context.trait(trait) >= threshold,
        detail=f"{trait} >= {threshold:g}",
    )


def event_tree(event_type: str) -> Node:
    """Build the decision tree for a known event type.

    Unknown events intentionally fall back to a simple observe action so the
    engine can preserve the FSM-driven state action during migration.
    """

    if event_type == "player_stole":
        return Selector(
            "player_stole",
            [
                Sequence("player_stole_chase", [trait_at_least("aggressive", 60), Action("chase", "chase")]),
                Sequence("player_stole_confront", [trait_at_least("bravery", 50), Action("confront", "confront")]),
                Action("player_stole_report", "report"),
            ],
        )

    if event_type == "player_attacked_ally":
        return Selector(
            "player_attacked_ally",
            [
                Sequence("ally_attack_brave", [trait_at_least("bravery", 70), Action("attack_from_bravery", "attack")]),
                Sequence("ally_attack_aggressive", [trait_at_least("aggressive", 50), Action("attack_from_aggression", "attack")]),
                Action("ally_attack_fallback", "cower"),
            ],
        )

    if event_type == "npc_under_attack":
        return Selector(
            "npc_under_attack",
            [
                Sequence("self_defend", [trait_at_least("bravery", 40), Action("defend", "defend")]),
                Action("self_flee", "flee"),
            ],
        )

    if event_type == "threat_detected":
        return Selector(
            "threat_detected",
            [
                Sequence("threat_brave", [trait_at_least("bravery", 60), Action("investigate_threat", "investigate")]),
                Sequence("threat_curious", [trait_at_least("curiosity", 50), Action("inspect_threat", "investigate")]),
                Action("threat_hide", "hide"),
            ],
        )

    if event_type == "sound_loud":
        return Selector(
            "sound_loud",
            [
                Sequence("loud_sound_curious", [trait_at_least("curiosity", 40), Action("investigate_loud_sound", "investigate")]),
                Action("loud_sound_ignore", "ignore"),
            ],
        )

    if event_type == "player_helped_npc":
        return Selector(
            "player_helped_npc",
            [
                Sequence("help_friendly", [trait_at_least("friendly", 30), Action("thank_player", "thank")]),
                Action("help_acknowledge", "acknowledge"),
            ],
        )

    if event_type == "player_completed_quest":
        return Selector(
            "player_completed_quest",
            [
                Sequence("quest_friendly", [trait_at_least("friendly", 20), Action("celebrate_completion", "celebrate")]),
                Action("quest_acknowledge", "acknowledge"),
            ],
        )

    if event_type == "give_gift":
        return Selector(
            "give_gift",
            [
                Sequence("gift_greedy", [trait_at_least("greedy", 60), Action("accept_eagerly", "accept_eagerly")]),
                Sequence("gift_friendly", [trait_at_least("friendly", 40), Action("thank_for_gift", "thank")]),
                Action("gift_accept", "accept"),
            ],
        )

    if event_type == "player_said_hello":
        return Selector(
            "player_said_hello",
            [
                Sequence("hello_friendly", [trait_at_least("friendly", 50), Action("greet_warmly", "greet_warmly")]),
                Action("hello_greet", "greet"),
            ],
        )

    if event_type == "vision_spotted":
        return Selector(
            "vision_spotted",
            [
                Sequence("vision_aggressive", [trait_at_least("aggressive", 60), Action("watch_closely", "watch_closely")]),
                Sequence("vision_curious", [trait_at_least("curiosity", 50), Action("observe", "observe")]),
                Action("vision_ignore", "ignore"),
            ],
        )

    if event_type == "sound_heard":
        return Selector(
            "sound_heard",
            [
                Sequence("sound_curious", [trait_at_least("curiosity", 40), Action("investigate_sound", "investigate_sound")]),
                Sequence("sound_brave", [trait_at_least("bravery", 60), Action("move_toward_sound", "move_toward_sound")]),
                Action("sound_stay_put", "stay_put"),
            ],
        )

    return Action("default_observe", "observe")


def evaluate_tree(event_type: str, context: Any) -> DecisionOutcome:
    """Evaluate the event-specific tree for the provided context."""

    return event_tree(event_type).evaluate(context)
