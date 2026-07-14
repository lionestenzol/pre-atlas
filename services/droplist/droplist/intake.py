"""Intake chainer — the bouncer in front of the drop pipeline.

Raw input arrives from the outside world (HTTP POST, CLI, file inbox). Before
it is allowed to become a Work Packet we run two gates:

  1. Noise gate  — empty / too-short input is dropped, never stored.
  2. Delta gate  — input whose normalized hash already exists is a zero-delta
                   duplicate; dropped so the drop list stays one-fact-per-row.

Survivors are handed to ``engine.process_drop`` (normalize -> classify ->
retrieve -> route -> complete -> store), which is the existing "chainer". The
return shape mirrors the webhook contract: ``status`` is ``secured`` or
``dropped``, and the ``delta_hash`` is returned either way so the caller can
see what was (or would have been) locked in.

This module adds NO new classification or storage logic — it composes what
hashing/engine/storage already provide. See
~/.claude/rules/common/assemble-first.md.
"""

from __future__ import annotations

import os

from . import dropstore, engine, storage
from .hashing import input_hash, normalize

# Inputs shorter than this (after normalization) are treated as noise. Tunable
# so a different intake source (e.g. structured webhook) can relax it.
MIN_CHARS = int(os.environ.get("DROPLIST_INTAKE_MIN_CHARS", "3"))


def chain_intake(raw: str, make_ship: bool = False) -> dict:
    """Run raw input through the bouncer, then the chainer.

    Returns a dict shaped for the webhook contract:
      secured -> {status, delta_hash, drop_id, category, type, title, confidence}
      dropped -> {status, reason, delta_hash}
    Never raises on bad classification — engine.process_drop falls back to the
    deterministic heuristic. Only a genuine storage/IO fault propagates.
    """
    norm = normalize(raw or "")
    h = input_hash(norm)

    # Bouncer gate 1 — noise (cheap, local; reject before any classify work).
    if len(norm) < MIN_CHARS:
        return {
            "status": "dropped",
            "reason": "noise: input below minimum length",
            "delta_hash": h,
        }

    # Chainer: build the packet WITHOUT persisting, then let the store's
    # insert_if_new be the single dedup authority. Under JSONL this is a
    # read-then-append; under a hosted backend it becomes an atomic
    # UNIQUE(input_hash) insert that makes concurrent multi-device drops safe.
    packet, ship = engine.process_drop(raw, make_ship=make_ship, persist=False)

    store = dropstore.get_store()
    # Bouncer gate 2 — zero-delta duplicate.
    if not store.insert_if_new(packet.to_dict()):
        return {
            "status": "dropped",
            "reason": "duplicate: delta_hash already secured",
            "delta_hash": packet.input_hash,
        }

    # Secured: persist the optional Mini Ship (a separate collection, not part
    # of the drop-list repo) only now that the packet itself is locked in.
    if ship is not None:
        storage.append(storage.MINI_SHIPS, ship.to_dict())

    # Spine wire: a nervous system builds the graph by default, not only when
    # the Atlas/lattice signal wire is on. DROPLIST_AUTOBUILD_DAGS (default on)
    # settles every secured drop into a DAG; DROPLIST_ATLAS_SIGNALS_URL still
    # gates Signal.v1 *emission* independently inside graph_engine, so build
    # and emit stay decoupled. Fail-soft so a graph fault never undoes a
    # secured drop. See ~/.claude/rules/common/code-as-furniture.md.
    if (os.environ.get("DROPLIST_AUTOBUILD_DAGS", "1") != "0"
            or os.environ.get("DROPLIST_ATLAS_SIGNALS_URL")):
        try:
            from . import graph_engine
            graph_engine.run_graph_from_packet(packet)
        except Exception:  # noqa: BLE001 — the secured drop stands regardless
            pass

    result = {
        "status": "secured",
        "delta_hash": packet.input_hash,
        "drop_id": packet.drop_id,
        "category": packet.domain,
        "type": packet.type,
        "title": packet.next_action or packet.normalized_input[:80],
        "confidence": packet.confidence,
    }
    if ship is not None:
        result["ship_id"] = ship.ship_id
    return result
