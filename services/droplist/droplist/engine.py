"""The core loop, assembled.

Drop -> Normalize -> Classify -> Retrieve -> Route -> Complete -> (Mini Ship) -> Log

Exactly one Work Packet per drop. Side effects (append to packets.jsonl,
llm_calls.jsonl) happen here so callers just get the packet back.
"""

from __future__ import annotations

import time
import uuid

from . import classifier, completion, dropstore, retrieval, router, storage
from .hashing import ClassificationCache, input_hash, normalize
from .schema import MiniShipPacket, WorkPacket

# which work-packet shapes become a Mini Ship, and what ship_type they map to
_SHIP_TYPE_BY = {
    ("problem", "build_product"): "feature",
    ("task", "build_product"): "feature",
    ("project", "build_product"): "prototype",
    ("idea", "build_product"): "needs_clarification",
    ("task", "file_ops"): "cleanup_pass",
    ("asset", "file_ops"): "cleanup_pass",
    ("problem", "file_ops"): "cleanup_pass",
    ("asset", "money_admin"): "tracker",
    ("task", "money_admin"): "tracker",
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _drop_id() -> str:
    return "drop_" + uuid.uuid4().hex[:12]


def process_drop(
    raw: str, make_ship: bool = False, persist: bool = True
) -> tuple[WorkPacket, MiniShipPacket | None]:
    """Build a Work Packet from raw input. Persists it by default.

    persist=False builds and returns the packet (and ship) WITHOUT writing —
    the intake valve uses this so the store's atomic insert_if_new is the
    single dedup authority. Callers that want plain capture keep the default.
    """
    norm = normalize(raw)
    h = input_hash(norm)

    store = dropstore.get_store()
    prior = store.read_all()
    cache = ClassificationCache(prior)

    cls = classifier.classify(norm, h, cache)
    context = retrieval.retrieve(norm, prior, k=5)
    workflow = router.select_workflow(cls["type"], cls["domain"])
    current, nxt = router.first_and_next(workflow)

    packet = WorkPacket(
        drop_id=_drop_id(),
        created_at=_now(),
        raw_input=raw,
        normalized_input=norm,
        input_hash=h,
        type=cls["type"],
        domain=cls["domain"],
        entities=cls["entities"],
        retrieved_context=context,
        selected_workflow=workflow,
        current_node=current,
        next_node=nxt,
        confidence=cls["confidence"],
    )
    completion.complete(packet)

    if persist:
        store.append(packet.to_dict())

    ship = None
    if make_ship:
        ship = to_mini_ship(packet)
        if persist:
            storage.append(storage.MINI_SHIPS, ship.to_dict())

    return packet, ship


def ship_from(drop_id: str) -> MiniShipPacket | None:
    """Load a stored packet by id, convert to a Mini Ship, and persist it."""
    for p in storage.read_all(storage.PACKETS):
        if p.get("drop_id") == drop_id:
            packet = WorkPacket(**{k: p[k] for k in WorkPacket().__dict__ if k in p})
            ship = to_mini_ship(packet)
            storage.append(storage.MINI_SHIPS, ship.to_dict())
            return ship
    return None


def to_mini_ship(packet: WorkPacket) -> MiniShipPacket:
    """Convert a routed Work Packet into the smallest complete output."""
    ship_type = _SHIP_TYPE_BY.get((packet.type, packet.domain), "needs_clarification")
    assignee = packet.assigned_to if packet.assigned_to in {
        "me", "claude_code", "script", "claude", "spark", "human_helper"
    } else "me"

    return MiniShipPacket(
        ship_id="ship_" + uuid.uuid4().hex[:12],
        created_at=_now(),
        source_drop_id=packet.drop_id,
        ship_type=ship_type,
        goal=packet.next_action,
        definition_of_done=packet.stop_condition,
        inputs=[e for e in packet.entities] or [packet.normalized_input[:80]],
        outputs=[],
        assigned_to=assignee,
        time_box="30m",
        allowed_actions=packet.allowed_actions,
        blocked_actions=packet.blocked_actions,
        test="manual: confirm the definition_of_done is met before marking shipped",
        feedback_signal="did this remove burden or create more?",
        status="ready" if ship_type != "needs_clarification" else "parked",
    )
