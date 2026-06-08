"""Routing: (type, domain) -> workflow, and the ordered DAG node lists.

The DAG is what stops wandering. Each workflow is an ordered list of nodes;
the router picks the workflow and reports current_node / next_node. Completion
logic (in completion.py) reads the node to decide the concrete next action.
"""

from __future__ import annotations

WORKFLOW_MAP: dict[tuple[str, str], str] = {
    ("task", "build_product"): "build_product_dag",
    ("problem", "build_product"): "build_product_dag",
    ("idea", "build_product"): "build_product_dag",
    ("project", "build_product"): "build_product_dag",
    ("decision", "build_product"): "build_product_dag",

    ("asset", "file_ops"): "file_ops_dag",
    ("problem", "file_ops"): "file_ops_dag",
    ("task", "file_ops"): "file_ops_dag",

    ("log", "animal_property"): "animal_obs_dag",
    ("warning", "animal_property"): "animal_obs_dag",
    ("task", "animal_property"): "animal_obs_dag",

    ("asset", "money_admin"): "money_admin_dag",
    ("task", "money_admin"): "money_admin_dag",
    ("follow_up", "money_admin"): "money_admin_dag",
    ("problem", "money_admin"): "money_admin_dag",

    ("task", "daily_command"): "daily_command_dag",
    ("follow_up", "daily_command"): "daily_command_dag",
}

FALLBACK_WORKFLOW = "general_dag"

DAGS: dict[str, list[str]] = {
    "file_ops_dag": [
        "inventory_metadata", "cluster_inventory", "select_priority_clusters",
        "deep_read_selected", "cleanup_plan", "ask_before_move_delete", "update_memory",
    ],
    "build_product_dag": [
        "identify_project", "retrieve_specs", "classify_bug_feature_architecture",
        "create_build_packet", "assign_to_claude_code_or_human", "test_or_review", "log_result",
    ],
    "animal_obs_dag": [
        "identify_entity_location", "retrieve_history",
        "classify_observation_issue_growth_feeding_breeding", "flag_abnormal",
        "create_log_entry", "schedule_followup_if_needed", "update_memory",
    ],
    "money_admin_dag": [
        "extract_entity_date_amount_deadline", "classify_bill_receipt_appointment_followup",
        "retrieve_related_status", "create_tracker_entry", "assign_action",
        "set_followup", "update_memory",
    ],
    "daily_command_dag": [
        "pull_open_packets", "retrieve_deadlines_unresolved_items", "group_by_domain",
        "choose_top_3_moves", "list_urgent_admin", "list_waiting_on",
        "list_decisions_needed", "output_brief",
    ],
    "general_dag": [
        "clarify_intent", "classify_or_ask", "route_or_park", "update_memory",
    ],
}


def select_workflow(dtype: str, domain: str) -> str:
    return WORKFLOW_MAP.get((dtype, domain), FALLBACK_WORKFLOW)


def nodes_for(workflow: str) -> list[str]:
    return DAGS.get(workflow, DAGS[FALLBACK_WORKFLOW])


def first_and_next(workflow: str) -> tuple[str, str]:
    nodes = nodes_for(workflow)
    current = nodes[0] if nodes else ""
    nxt = nodes[1] if len(nodes) > 1 else ""
    return current, nxt
