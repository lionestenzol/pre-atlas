"""Packet completion: fill the action fields after classify/retrieve/route.

This is the operator brain. For each workflow it answers:
  who/what handles the next step, what is the ONE next action, when does it
  stop, what is allowed, what is blocked, does a human need to decide, and
  what should Atlas remember.

Hard rules (enforced here, not suggested):
  - exactly one concrete next_action, no plans
  - always a stop_condition
  - always blocked_actions; nothing dispatches automatically
  - low confidence or risk flips needs_human_decision = True
"""

from __future__ import annotations

import time

from . import llm
from .schema import WorkPacket

# actions every packet blocks: the engine never acts on its own
_GLOBAL_BLOCKED = ["dispatch_automatically", "execute_without_approval"]

_LOW_CONFIDENCE = 0.55


def _abnormal(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in (
        "limping", "sick", "dying", "bleeding", "urgent", "won't", "abnormal",
        "not eating", "wound", "blood", "emergency",
    ))


def _build_action(packet: WorkPacket) -> dict:
    t = packet.type
    text = packet.normalized_input.lower()
    if t == "decision":
        return {
            "assigned_to": "claude",
            "next_action": "save as product architecture decision",
            "stop_condition": "decision recorded in Atlas with rationale; no code yet",
            "allowed_actions": ["record_decision", "update_specs", "link_related_packets"],
            "blocked_actions": ["full_redesign", "write_code", "delete_existing_specs"],
            "status": "logged",
        }
    if t == "idea":
        return {
            "assigned_to": "claude",
            "next_action": "capture idea and link to owning project; do not build yet",
            "stop_condition": "idea logged against a project; flagged for later scoping",
            "allowed_actions": ["record_idea", "link_project", "tag_for_review"],
            "blocked_actions": ["full_redesign", "start_building"],
            "status": "logged",
        }
    if t == "problem" or ("bug" in text or "crash" in text):
        return {
            "assigned_to": "claude_code",
            "next_action": "reproduce and isolate the failure in the smallest test case",
            "stop_condition": "failure reproduced and root cause located; fix not yet applied",
            "allowed_actions": ["read_code", "write_failing_test", "isolate_repro"],
            "blocked_actions": ["full_redesign", "force_push", "delete_files"],
            "status": "routed",
        }
    if t in ("task", "project"):
        return {
            "assigned_to": "claude_code",
            "next_action": "scope the smallest shippable change and draft a Mini Ship packet",
            "stop_condition": "one bounded build task defined with a definition of done",
            "allowed_actions": ["scope_change", "draft_mini_ship", "retrieve_specs"],
            "blocked_actions": ["full_redesign", "build_unscoped_feature"],
            "status": "routed",
        }
    return {
        "assigned_to": "claude",
        "next_action": "identify the owning project and retrieve its specs",
        "stop_condition": "project identified and relevant specs surfaced",
        "allowed_actions": ["identify_project", "retrieve_specs"],
        "blocked_actions": ["full_redesign"],
        "status": "routed",
    }


def _file_ops_action(packet: WorkPacket) -> dict:
    return {
        "assigned_to": "script",
        "next_action": "create metadata-only file inventory",
        "stop_condition": "inventory written (paths, sizes, mtimes, hashes); no contents read",
        "allowed_actions": ["list_paths", "read_metadata", "hash_files", "cluster_by_metadata"],
        "blocked_actions": ["delete_files", "move_files", "deep_read_all_files"],
        "status": "routed",
    }


def _animal_action(packet: WorkPacket) -> dict:
    abnormal = _abnormal(packet.normalized_input)
    if abnormal or packet.type == "warning":
        return {
            "assigned_to": "me",
            "next_action": "inspect the animal/site now and record condition with a photo",
            "stop_condition": "condition assessed; vet contact decided yes/no",
            "allowed_actions": ["inspect", "photo", "log_condition", "flag_vet"],
            "blocked_actions": ["ignore", "auto_schedule_vet"],
            "needs_human_decision": True,
            "status": "waiting",
        }
    return {
        "assigned_to": "me",
        "next_action": "log observation and schedule follow-up photo/check",
        "stop_condition": "observation logged and follow-up date set",
        "allowed_actions": ["log_observation", "schedule_followup", "attach_photo"],
        "blocked_actions": ["auto_intervene"],
        "needs_human_decision": False,
        "status": "logged",
    }


def _money_action(packet: WorkPacket) -> dict:
    text = packet.type
    if text == "follow_up":
        return {
            "assigned_to": "me",
            "next_action": "check status of the outstanding item and set a follow-up date",
            "stop_condition": "current status confirmed and next check scheduled",
            "allowed_actions": ["check_status", "set_followup", "update_tracker"],
            "blocked_actions": ["authorize_payment", "send_message"],
            "status": "waiting",
        }
    if text == "asset":
        return {
            "assigned_to": "script",
            "next_action": "extract date/entity/amount and create tracker entry",
            "stop_condition": "tracker row written with date, entity, amount, due date",
            "allowed_actions": ["extract_fields", "create_tracker_entry"],
            "blocked_actions": ["authorize_payment", "send_message"],
            "status": "logged",
        }
    return {
        "assigned_to": "me",
        "next_action": "create a tracker entry and assign the concrete admin action",
        "stop_condition": "tracker entry created with owner and deadline",
        "allowed_actions": ["extract_fields", "create_tracker_entry", "assign_action"],
        "blocked_actions": ["authorize_payment", "send_message"],
        "status": "routed",
    }


def _daily_command_action(packet: WorkPacket) -> dict:
    return {
        "assigned_to": "me",
        "next_action": "pull open/waiting packets, group by domain, surface top 3 moves",
        "stop_condition": "brief printed: top 3 moves, urgent admin, waiting-on, decisions needed",
        "allowed_actions": ["read_packets", "filter_open", "group_by_domain"],
        "blocked_actions": ["dispatch_actions"],
        "status": "routed",
    }


def _general_action(packet: WorkPacket) -> dict:
    return {
        "assigned_to": "me",
        "next_action": "clarify intent — what should happen with this, and which project owns it",
        "stop_condition": "intent clarified and a domain/type assigned",
        "allowed_actions": ["ask_clarifying_question", "reclassify"],
        "blocked_actions": ["act_on_ambiguous_input"],
        "needs_human_decision": True,
        "status": "open",
    }


_COMPLETERS = {
    "file_ops_dag": _file_ops_action,
    "build_product_dag": _build_action,
    "animal_obs_dag": _animal_action,
    "money_admin_dag": _money_action,
    "daily_command_dag": _daily_command_action,
    "general_dag": _general_action,
}


def complete(packet: WorkPacket) -> WorkPacket:
    """Fill action fields on the packet in place and return it."""
    t0 = time.time()
    completer = _COMPLETERS.get(packet.selected_workflow, _general_action)
    fields = completer(packet)

    packet.assigned_to = fields["assigned_to"]
    packet.next_action = fields["next_action"]
    packet.stop_condition = fields["stop_condition"]
    packet.allowed_actions = fields["allowed_actions"]
    packet.blocked_actions = fields["blocked_actions"] + _GLOBAL_BLOCKED
    packet.status = fields.get("status", "routed")
    packet.needs_human_decision = fields.get("needs_human_decision", False)

    # confidence gate: anything we're unsure about needs a human
    if packet.confidence < _LOW_CONFIDENCE:
        packet.needs_human_decision = True

    ent = ", ".join(packet.entities[:3]) if packet.entities else packet.type
    packet.memory_update = (
        f"{packet.type}/{packet.domain}: {ent} -> {packet.next_action} "
        f"(assigned: {packet.assigned_to}, status: {packet.status})"
    )

    llm.log_call(
        "packet_completion", "heuristic-v1", packet.input_hash,
        packet.normalized_input, packet.next_action,
        int((time.time() - t0) * 1000), "success",
    )
    return packet
