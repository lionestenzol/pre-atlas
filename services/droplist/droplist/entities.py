"""Entity store: the long-lived things drops attach to.

An entity (animal, project, person, asset) has stable identity, a history of
observations, and the DAGs that touched it. Drops resolve to entities
deterministically by canonical token, so a drop today about "the doe" attaches
to the same RABBIT entity a drop made last week.
"""

from __future__ import annotations

import json
import os
import re

from . import clock, storage

# canonical token -> (entity_type, canonical_name)
_TOKEN_MAP = {
    "droplist": ("project", "DropList"),
    "atlas": ("project", "Atlas"),
    "rabbit": ("animal", "Rabbits"), "rabbits": ("animal", "Rabbits"),
    "doe": ("animal", "Doe"), "buck": ("animal", "Buck"),
    "goat": ("animal", "Goats"), "goats": ("animal", "Goats"),
    "chicken": ("animal", "Chickens"), "chickens": ("animal", "Chickens"),
    "bsfl": ("asset", "BSFL bins"),
}


def _dir() -> str:
    storage.ensure_data_dir()
    d = os.path.join(storage.DATA_DIR, "entities")
    os.makedirs(d, exist_ok=True)
    return d


def _path(entity_id: str) -> str:
    return os.path.join(_dir(), f"{entity_id}.json")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _id(etype: str, name: str) -> str:
    return f"{etype.upper()}-{_slug(name).upper()}"


def get(entity_id: str) -> dict | None:
    p = _path(entity_id)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(ent: dict) -> None:
    with open(_path(ent["entity_id"]), "w", encoding="utf-8") as f:
        json.dump(ent, f, ensure_ascii=False, indent=2)


def list_all() -> list[dict]:
    out = []
    for fn in sorted(os.listdir(_dir())):
        if fn.endswith(".json"):
            with open(os.path.join(_dir(), fn), encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def resolve_from_packet(packet_dict: dict) -> list[str]:
    """Return entity_ids referenced by this drop, creating any that are new."""
    text = packet_dict.get("normalized_input", "").lower()
    found: list[str] = []
    seen = set()

    # numbered animals like "doe 3" -> ANIMAL-DOE-3
    for m in re.finditer(r"\b(doe|buck|goat|chicken|rabbit)\s+(\d+)\b", text):
        name = f"{m.group(1).title()} {m.group(2)}"
        eid = _id("animal", name)
        if eid not in seen:
            _ensure(eid, "animal", name)
            found.append(eid); seen.add(eid)

    for tok, (etype, cname) in _TOKEN_MAP.items():
        if re.search(rf"\b{re.escape(tok)}\b", text):
            eid = _id(etype, cname)
            if eid not in seen:
                _ensure(eid, etype, cname)
                found.append(eid); seen.add(eid)

    return found


def _ensure(eid: str, etype: str, name: str) -> dict:
    ent = get(eid)
    if ent is None:
        ent = {
            "entity_id": eid, "name": name, "type": etype,
            "related_dags": [], "open_nodes": [],
            "observations": [], "last_observation": "",
            "next_check": "", "created_at": clock.now_iso(),
        }
        save(ent)
    return ent


def attach_dag(entity_id: str, dag_id: str, observation: str = "") -> None:
    ent = get(entity_id)
    if ent is None:
        return
    if dag_id not in ent["related_dags"]:
        ent["related_dags"].append(dag_id)
    if observation:
        ent["observations"].append({"at": clock.now_iso(), "text": observation})
        ent["last_observation"] = observation
    ent["updated_at"] = clock.now_iso()
    save(ent)
