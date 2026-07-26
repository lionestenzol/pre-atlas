"""Dispatcher: the control layer. A node is runnable iff it is `ready` and all
of its dependencies are `done`. This is the spine of MVP 2 — everything else
just feeds it."""

from __future__ import annotations


def get_ready_nodes(dag: dict) -> list[dict]:
    done = {n["id"] for n in dag["nodes"] if n["status"] == "done"}
    ready = []
    for node in dag["nodes"]:
        if node["status"] != "ready":
            continue
        if all(dep in done for dep in node.get("depends_on", [])):
            ready.append(node)
    return ready


def get_node(dag: dict, node_id: str) -> dict | None:
    for n in dag["nodes"]:
        if n["id"] == node_id:
            return n
    return None
