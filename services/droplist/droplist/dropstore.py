"""Drop-list storage backend — the swappable seam for the drop list.

The drop list (``packets.jsonl`` today) is the single source of truth. This
module puts a thin Repository in front of it so the *backend* can change
without touching the engine or the intake valve.

Backend is chosen by the ``DROPLIST_STORE`` env var:

  - ``jsonl`` (default): append-only JSONL via the existing ``storage`` module.
    Zero dependencies, single-writer. Dedup is read-then-append — fine when one
    process owns the file.
  - ``supabase`` (NOT YET BUILT): a hosted Postgres table with
    ``UNIQUE(input_hash)``, so dedup is ATOMIC across concurrent writers — the
    one capability JSONL cannot give us and the whole reason multi-device
    intake needs it. When added, ``insert_if_new`` becomes
    ``insert ... on conflict (input_hash) do nothing`` and the swap is just
    this env var (plus a live Supabase project). The seam is ready now.

See the ``project_four_part_pipeline_topology`` memory for why this exists.

Interface (DropStore):
  read_all()            -> every packet (engine context/cache/retrieval)
  append(packet)        -> unconditional persist (engine default + inventory)
  insert_if_new(packet) -> persist only if input_hash is new; returns
                           True=secured (newly stored) / False=duplicate.
                           The authoritative dedup point — intake trusts this.
"""

from __future__ import annotations

import os
from typing import Protocol

from . import storage


class DropStore(Protocol):
    """The drop-list repository contract. Every backend implements these."""

    def read_all(self) -> list[dict]: ...
    def append(self, packet: dict) -> None: ...
    def insert_if_new(self, packet: dict) -> bool: ...


class JsonlDropStore:
    """Append-only JSONL backend (the default). Delegates to ``storage``.

    Behaviour is byte-for-byte what the engine did before this seam existed:
    ``append`` is unconditional, ``read_all`` reads ``packets.jsonl``.
    """

    def read_all(self) -> list[dict]:
        return storage.read_all(storage.PACKETS)

    def append(self, packet: dict) -> None:
        storage.append(storage.PACKETS, packet)

    def insert_if_new(self, packet: dict) -> bool:
        h = packet.get("input_hash", "")
        # Read-then-append. Safe for the single-writer JSONL model; a hosted
        # backend replaces this with an atomic UNIQUE-constraint insert so
        # concurrent writers can't both win.
        existing = {p.get("input_hash", "") for p in self.read_all()}
        if h in existing:
            return False
        self.append(packet)
        return True


_BACKENDS: dict[str, type] = {"jsonl": JsonlDropStore}


def get_store() -> DropStore:
    """Return a DropStore for the configured backend.

    Backends are stateless, so a fresh instance per call is cheap and avoids
    cached-singleton surprises when tests flip ``DROPLIST_STORE``. A future
    networked backend (Supabase) can introduce its own connection caching.
    """
    name = os.environ.get("DROPLIST_STORE", "jsonl").lower()
    if name == "supabase":
        raise NotImplementedError(
            "DROPLIST_STORE=supabase: SupabaseDropStore is not built yet. "
            "Un-pause the Supabase project and implement the backend "
            "(UNIQUE(input_hash) on-conflict insert). The seam is wired — only "
            "the backend class is missing."
        )
    backend = _BACKENDS.get(name)
    if backend is None:
        raise ValueError(
            f"DROPLIST_STORE={name!r} is not a known backend "
            f"(choose from {sorted(_BACKENDS)} or 'supabase')."
        )
    return backend()
