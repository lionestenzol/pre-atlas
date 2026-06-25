"""Schemas for Work Packets and Mini Ship Packets.

This is the contract. Everything in the system either produces or consumes
one of these two objects. Enums are closed sets — a packet that uses a value
outside the allowed set is invalid and will fail validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# ---- Closed enum sets (the only legal values) ----------------------------

TYPES = {
    "task", "log", "idea", "project", "asset",
    "decision", "follow_up", "problem", "reference", "warning",
}

DOMAINS = {
    "file_ops", "build_product", "animal_property", "money_admin",
    "daily_command", "people_admin", "food_health", "general",
}

ASSIGNEES = {
    "me", "claude", "claude_code", "spark", "script",
    "calendar", "sheet", "human_helper",
}

PACKET_STATUS = {"open", "routed", "waiting", "shipped", "logged", "archived"}

SHIP_TYPES = {
    "script", "feature", "cleanup_pass", "report", "doc", "tracker",
    "workflow", "prompt_pack", "prototype", "needs_clarification",
}

SHIP_ASSIGNEES = {"me", "claude_code", "script", "claude", "spark", "human_helper"}

SHIP_STATUS = {"ready", "building", "shipped", "failed", "parked"}


# ---- Work Packet -----------------------------------------------------------


@dataclass
class WorkPacket:
    """The universal object. Exactly one is produced per drop."""

    drop_id: str = ""
    created_at: str = ""
    raw_input: str = ""
    normalized_input: str = ""
    input_hash: str = ""
    type: str = "task"
    domain: str = "general"
    entities: list[str] = field(default_factory=list)
    retrieved_context: list[dict[str, Any]] = field(default_factory=list)
    selected_workflow: str = ""
    current_node: str = ""
    next_node: str = ""
    assigned_to: str = "me"
    next_action: str = ""
    stop_condition: str = ""
    allowed_actions: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    needs_human_decision: bool = False
    memory_update: str = ""
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list == valid."""
        errors: list[str] = []
        if self.type not in TYPES:
            errors.append(f"type '{self.type}' not in allowed set")
        if self.domain not in DOMAINS:
            errors.append(f"domain '{self.domain}' not in allowed set")
        if self.assigned_to not in ASSIGNEES:
            errors.append(f"assigned_to '{self.assigned_to}' not in allowed set")
        if self.status not in PACKET_STATUS:
            errors.append(f"status '{self.status}' not in allowed set")
        if not self.selected_workflow:
            errors.append("selected_workflow is empty")
        if not self.next_action:
            errors.append("next_action is empty (every packet needs one concrete step)")
        if not self.stop_condition:
            errors.append("stop_condition is empty")
        if not isinstance(self.allowed_actions, list):
            errors.append("allowed_actions must be a list")
        if not isinstance(self.blocked_actions, list):
            errors.append("blocked_actions must be a list")
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"confidence {self.confidence} out of range [0,1]")
        return errors

    def is_valid(self) -> bool:
        return not self.validate()


# ---- Mini Ship Packet ------------------------------------------------------


@dataclass
class MiniShipPacket:
    """The smallest complete output/action derived from a Work Packet."""

    ship_id: str = ""
    created_at: str = ""
    source_drop_id: str = ""
    ship_type: str = "needs_clarification"
    goal: str = ""
    definition_of_done: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    assigned_to: str = "me"
    time_box: str = ""
    allowed_actions: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    test: str = ""
    feedback_signal: str = ""
    status: str = "ready"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.ship_type not in SHIP_TYPES:
            errors.append(f"ship_type '{self.ship_type}' not in allowed set")
        if self.assigned_to not in SHIP_ASSIGNEES:
            errors.append(f"assigned_to '{self.assigned_to}' not in allowed set")
        if self.status not in SHIP_STATUS:
            errors.append(f"status '{self.status}' not in allowed set")
        if not self.goal:
            errors.append("goal is empty")
        if not self.definition_of_done:
            errors.append("definition_of_done is empty")
        return errors

    def is_valid(self) -> bool:
        return not self.validate()
