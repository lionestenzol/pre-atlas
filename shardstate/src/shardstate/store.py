"""Content-addressed graph store.

Every value put into the store is hashed (BLAKE2b over canonical JSON) — that
hash is the node's identity in the immutable node table. Mutable entities live
in a separate table that maps stable_id -> current content_hash. The state root
is hashed over the sorted (stable_id, content_hash) pairs, so any change to any
entity yields a fresh state root that all parties can compare in one operation.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from . import clock as vc
from .hashing import canonical_json, hash_bytes, hash_value


SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    content_hash TEXT PRIMARY KEY,
    content_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    stable_id TEXT PRIMARY KEY,
    current_hash TEXT NOT NULL REFERENCES nodes(content_hash),
    vclock_json TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS states (
    state_hash TEXT PRIMARY KEY,
    parent_hash TEXT,
    index_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    created_by TEXT,
    seq INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS states_seq ON states(seq);

CREATE TABLE IF NOT EXISTS entity_history (
    stable_id TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    vclock_json TEXT NOT NULL,
    PRIMARY KEY (stable_id, state_hash)
);

CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stable_id TEXT NOT NULL,
    winning_hash TEXT NOT NULL,
    losing_hash TEXT NOT NULL,
    winning_clock TEXT NOT NULL,
    losing_clock TEXT NOT NULL,
    winning_agent TEXT NOT NULL,
    losing_agent TEXT NOT NULL,
    detected_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# --- Public types ------------------------------------------------------------


@dataclass(frozen=True)
class Ref:
    """A coordinate into the graph: which state, which node, what op label.

    `op` is metadata for the receiver — the store ignores it on resolve.
    """

    state: str
    node: str
    op: str = "read"

    def to_dict(self) -> Dict[str, str]:
        return {"state": self.state, "node": self.node, "op": self.op}

    @classmethod
    def from_dict(cls, d: Dict[str, str]) -> "Ref":
        return cls(state=d["state"], node=d["node"], op=d.get("op", "read"))


@dataclass(frozen=True)
class Node:
    id: str           # stable id
    hash: str         # content hash at time of return
    value: Any
    vclock: vc.VClock


@dataclass(frozen=True)
class State:
    hash: str
    parent: Optional[str]
    seq: int


@dataclass(frozen=True)
class Conflict:
    stable_id: str
    winning_hash: str
    losing_hash: str
    winning_agent: str
    losing_agent: str
    detected_at: float


class StoreError(Exception):
    pass


class NotFound(StoreError):
    pass


# --- Store -------------------------------------------------------------------


_DELETE = object()  # sentinel for patch-time deletion


class Store:
    """Content-addressed graph store, backed by SQLite.

    Every mutating method returns a `State` whose `.hash` is the new state
    root. A `Ref` made against that root pins the receiver to exactly the
    graph the sender saw.
    """

    def __init__(self, path: str | os.PathLike[str], agent_id: Optional[str] = None):
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self.agent_id = agent_id or self._load_or_create_agent_id()

    # -- agent id (persisted per-store so a single process has stable identity)
    def _load_or_create_agent_id(self) -> str:
        row = self._conn.execute("SELECT value FROM meta WHERE key='agent_id'").fetchone()
        if row:
            return row[0]
        new_id = f"agent_{uuid.uuid4().hex[:8]}"
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES('agent_id', ?)", (new_id,)
        )
        return new_id

    # -- low-level node storage
    def _store_node(self, value: Any) -> str:
        blob = canonical_json(value)
        h = hash_bytes(blob)
        self._conn.execute(
            "INSERT OR IGNORE INTO nodes(content_hash, content_json, created_at) VALUES(?, ?, ?)",
            (h, blob.decode("utf-8"), time.time()),
        )
        return h

    def _load_node(self, content_hash: str) -> Any:
        row = self._conn.execute(
            "SELECT content_json FROM nodes WHERE content_hash=?", (content_hash,)
        ).fetchone()
        if row is None:
            raise NotFound(f"node {content_hash} not in store")
        import json
        return json.loads(row[0])

    # -- state root computation
    def _compute_state_hash(self, index: List[Tuple[str, str, vc.VClock]]) -> str:
        # canonical: sort by stable_id; include hash + vclock so concurrent
        # writes that landed at the same content hash still produce distinct
        # state roots.
        ordered = sorted(index, key=lambda r: r[0])
        return hash_value([[sid, ch, sorted(vclock.items())] for sid, ch, vclock in ordered])

    def _current_index(self) -> List[Tuple[str, str, vc.VClock]]:
        import json
        rows = self._conn.execute(
            "SELECT stable_id, current_hash, vclock_json FROM entities ORDER BY stable_id"
        ).fetchall()
        return [(sid, ch, json.loads(vcj)) for sid, ch, vcj in rows]

    def _commit_state(self, parent: Optional[str]) -> State:
        import json
        index = self._current_index()
        state_hash = self._compute_state_hash(index)
        seq_row = self._conn.execute("SELECT COALESCE(MAX(seq), -1) FROM states").fetchone()
        seq = (seq_row[0] if seq_row else -1) + 1
        index_json = json.dumps(
            [[sid, ch, sorted(vclock.items())] for sid, ch, vclock in index],
            separators=(",", ":"),
        )
        # If this state already exists (no-op write), skip — but still return it.
        existing = self._conn.execute(
            "SELECT seq FROM states WHERE state_hash=?", (state_hash,)
        ).fetchone()
        if existing is not None:
            return State(hash=state_hash, parent=parent, seq=existing[0])
        self._conn.execute(
            "INSERT INTO states(state_hash, parent_hash, index_json, created_at, created_by, seq) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (state_hash, parent, index_json, time.time(), self.agent_id, seq),
        )
        # write entity_history rows for this state
        for sid, ch, vclock in index:
            self._conn.execute(
                "INSERT OR REPLACE INTO entity_history(stable_id, state_hash, content_hash, vclock_json) "
                "VALUES(?, ?, ?, ?)",
                (sid, state_hash, ch, json.dumps(vclock)),
            )
        return State(hash=state_hash, parent=parent, seq=seq)

    def _current_state_hash(self) -> Optional[str]:
        row = self._conn.execute(
            "SELECT state_hash FROM states ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    # -- public API: writes
    def put(
        self,
        value: Any,
        stable_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Node:
        """Insert a new entity, or replace one wholesale.

        Returns the Node and commits a new state root.
        """
        agent = agent_id or self.agent_id
        sid = stable_id or f"n_{uuid.uuid4().hex[:12]}"
        with self._lock, self._conn:
            content_hash = self._store_node(value)
            existing = self._conn.execute(
                "SELECT vclock_json FROM entities WHERE stable_id=?", (sid,)
            ).fetchone()
            import json
            if existing:
                clock = vc.increment(json.loads(existing[0]), agent)
            else:
                clock = vc.increment(vc.empty(), agent)
            self._conn.execute(
                "INSERT OR REPLACE INTO entities(stable_id, current_hash, vclock_json, updated_at) "
                "VALUES(?, ?, ?, ?)",
                (sid, content_hash, json.dumps(clock), time.time()),
            )
            parent = self._current_state_hash()
            self._commit_state(parent)
            return Node(id=sid, hash=content_hash, value=value, vclock=clock)

    def patch(
        self,
        stable_id: str,
        changes: Dict[str, Any],
        agent_id: Optional[str] = None,
    ) -> State:
        """Apply dotted-path field changes. Use the sentinel `Store.DELETE` to drop a key."""
        agent = agent_id or self.agent_id
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT current_hash, vclock_json FROM entities WHERE stable_id=?", (stable_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"entity {stable_id} not in store")
            import json
            current_hash, vclock_json = row
            value = self._load_node(current_hash)
            new_value = _apply_changes(value, changes)
            new_hash = self._store_node(new_value)
            new_clock = vc.increment(json.loads(vclock_json), agent)
            self._conn.execute(
                "UPDATE entities SET current_hash=?, vclock_json=?, updated_at=? WHERE stable_id=?",
                (new_hash, json.dumps(new_clock), time.time(), stable_id),
            )
            parent = self._current_state_hash()
            return self._commit_state(parent)

    DELETE = _DELETE

    def append(
        self,
        stable_id: str,
        path: str,
        value: Any,
        agent_id: Optional[str] = None,
    ) -> State:
        """Append `value` to the list at `path` inside `stable_id`."""
        agent = agent_id or self.agent_id
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT current_hash, vclock_json FROM entities WHERE stable_id=?", (stable_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"entity {stable_id} not in store")
            import json
            current_hash, vclock_json = row
            cur_value = self._load_node(current_hash)
            target = _resolve_path(cur_value, path)
            if not isinstance(target, list):
                raise StoreError(f"path {path!r} is not a list (got {type(target).__name__})")
            new_value = _apply_changes(cur_value, {path: target + [value]})
            new_hash = self._store_node(new_value)
            new_clock = vc.increment(json.loads(vclock_json), agent)
            self._conn.execute(
                "UPDATE entities SET current_hash=?, vclock_json=?, updated_at=? WHERE stable_id=?",
                (new_hash, json.dumps(new_clock), time.time(), stable_id),
            )
            parent = self._current_state_hash()
            return self._commit_state(parent)

    def merge_remote(
        self,
        stable_id: str,
        remote_value: Any,
        remote_clock: vc.VClock,
        remote_agent: str,
    ) -> State:
        """Apply a write from another agent. Detects concurrency, logs conflicts.

        Last-writer-wins by remote_agent timestamp arrival; on a tie (concurrent
        writes), the lexicographically larger agent_id wins. Both happen-before
        the local clock would make this a no-op; remote dominating local
        accepts the remote write outright.
        """
        with self._lock, self._conn:
            import json
            row = self._conn.execute(
                "SELECT current_hash, vclock_json FROM entities WHERE stable_id=?", (stable_id,)
            ).fetchone()
            now = time.time()
            if row is None:
                # no local entity — accept remote outright
                content_hash = self._store_node(remote_value)
                self._conn.execute(
                    "INSERT INTO entities(stable_id, current_hash, vclock_json, updated_at) "
                    "VALUES(?, ?, ?, ?)",
                    (stable_id, content_hash, json.dumps(remote_clock), now),
                )
                parent = self._current_state_hash()
                return self._commit_state(parent)

            local_hash, local_clock_json = row
            local_clock = json.loads(local_clock_json)
            if vc.dominates(local_clock, remote_clock):
                # local is strictly newer; remote is stale, ignore
                return State(
                    hash=self._current_state_hash(),  # type: ignore[arg-type]
                    parent=None,
                    seq=self._conn.execute("SELECT MAX(seq) FROM states").fetchone()[0],
                )
            if vc.dominates(remote_clock, local_clock):
                # remote dominates; accept
                content_hash = self._store_node(remote_value)
                self._conn.execute(
                    "UPDATE entities SET current_hash=?, vclock_json=?, updated_at=? WHERE stable_id=?",
                    (content_hash, json.dumps(remote_clock), now, stable_id),
                )
                parent = self._current_state_hash()
                return self._commit_state(parent)
            # concurrent — log conflict, resolve by lex-larger agent_id (LWW deterministic)
            remote_hash = self._store_node(remote_value)
            local_agents = [a for a in local_clock]
            local_agent = max(local_agents) if local_agents else self.agent_id
            if remote_agent > local_agent:
                winner_hash, winner_clock, winner_agent = remote_hash, vc.merge(local_clock, remote_clock), remote_agent
                loser_hash, loser_clock, loser_agent = local_hash, local_clock, local_agent
            else:
                winner_hash, winner_clock, winner_agent = local_hash, vc.merge(local_clock, remote_clock), local_agent
                loser_hash, loser_clock, loser_agent = remote_hash, remote_clock, remote_agent
            self._conn.execute(
                "INSERT INTO conflicts(stable_id, winning_hash, losing_hash, winning_clock, losing_clock, "
                "winning_agent, losing_agent, detected_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (stable_id, winner_hash, loser_hash, json.dumps(winner_clock),
                 json.dumps(loser_clock), winner_agent, loser_agent, now),
            )
            self._conn.execute(
                "UPDATE entities SET current_hash=?, vclock_json=?, updated_at=? WHERE stable_id=?",
                (winner_hash, json.dumps(winner_clock), now, stable_id),
            )
            parent = self._current_state_hash()
            return self._commit_state(parent)

    # -- public API: reads
    def get(self, stable_id: str, state: Optional[str] = None) -> Any:
        """Return the value of `stable_id` at `state` (defaults to current)."""
        import json
        if state is None:
            row = self._conn.execute(
                "SELECT current_hash FROM entities WHERE stable_id=?", (stable_id,)
            ).fetchone()
            if row is None:
                raise NotFound(f"entity {stable_id} not in store")
            return self._load_node(row[0])
        row = self._conn.execute(
            "SELECT content_hash FROM entity_history WHERE stable_id=? AND state_hash=?",
            (stable_id, state),
        ).fetchone()
        if row is None:
            raise NotFound(f"entity {stable_id} not present in state {state}")
        return self._load_node(row[0])

    def resolve(self, ref: Ref) -> Any:
        """Resolve a Ref to its node value at the referenced state."""
        return self.get(ref.node, state=ref.state)

    def head(self) -> Optional[State]:
        row = self._conn.execute(
            "SELECT state_hash, parent_hash, seq FROM states ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return State(hash=row[0], parent=row[1], seq=row[2]) if row else None

    def diff(self, state_a: str, state_b: str) -> List[Dict[str, Any]]:
        """Per-entity changes from state_a → state_b. Returns added/removed/changed."""
        a = self._load_state_index(state_a)
        b = self._load_state_index(state_b)
        ids = set(a) | set(b)
        out: List[Dict[str, Any]] = []
        for sid in sorted(ids):
            ah = a.get(sid)
            bh = b.get(sid)
            if ah == bh:
                continue
            entry: Dict[str, Any] = {"stable_id": sid}
            if ah is None:
                entry["change"] = "added"
                entry["after"] = bh
            elif bh is None:
                entry["change"] = "removed"
                entry["before"] = ah
            else:
                entry["change"] = "changed"
                entry["before"] = ah
                entry["after"] = bh
            out.append(entry)
        return out

    def _load_state_index(self, state_hash: str) -> Dict[str, str]:
        import json
        row = self._conn.execute(
            "SELECT index_json FROM states WHERE state_hash=?", (state_hash,)
        ).fetchone()
        if row is None:
            raise NotFound(f"state {state_hash} not in store")
        return {sid: ch for sid, ch, _vc in json.loads(row[0])}

    def conflicts(self, stable_id: Optional[str] = None) -> List[Conflict]:
        if stable_id:
            rows = self._conn.execute(
                "SELECT stable_id, winning_hash, losing_hash, winning_agent, losing_agent, detected_at "
                "FROM conflicts WHERE stable_id=? ORDER BY id",
                (stable_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT stable_id, winning_hash, losing_hash, winning_agent, losing_agent, detected_at "
                "FROM conflicts ORDER BY id"
            ).fetchall()
        return [
            Conflict(
                stable_id=sid, winning_hash=wh, losing_hash=lh,
                winning_agent=wa, losing_agent=la, detected_at=t,
            )
            for sid, wh, lh, wa, la, t in rows
        ]

    def subscribe(
        self,
        since: Optional[str] = None,
        poll_interval: float = 0.1,
        stop_after: Optional[float] = None,
    ) -> Iterator[State]:
        """Yield each new State as it lands. Polling-based; cheap and honest."""
        last_seq = -1
        if since is not None:
            row = self._conn.execute(
                "SELECT seq FROM states WHERE state_hash=?", (since,)
            ).fetchone()
            if row is None:
                raise NotFound(f"state {since} not in store")
            last_seq = row[0]
        deadline = (time.monotonic() + stop_after) if stop_after else None
        while True:
            rows = self._conn.execute(
                "SELECT state_hash, parent_hash, seq FROM states WHERE seq > ? ORDER BY seq",
                (last_seq,),
            ).fetchall()
            for sh, ph, seq in rows:
                last_seq = seq
                yield State(hash=sh, parent=ph, seq=seq)
            if deadline is not None and time.monotonic() >= deadline:
                return
            time.sleep(poll_interval)

    def close(self) -> None:
        self._conn.close()

    # -- sync helpers ---------------------------------------------------------
    # These are intentionally minimal hooks for the sync protocol in `sync.py`.
    # They live on Store (rather than reaching into _conn from outside) so the
    # SQL surface remains contained and the sync module stays transport-shaped.

    def has_node(self, content_hash: str) -> bool:
        """Return True iff a node with this content hash is already stored."""
        row = self._conn.execute(
            "SELECT 1 FROM nodes WHERE content_hash=?", (content_hash,)
        ).fetchone()
        return row is not None

    def has_state(self, state_hash: str) -> bool:
        """Return True iff this state root is already stored."""
        row = self._conn.execute(
            "SELECT 1 FROM states WHERE state_hash=?", (state_hash,)
        ).fetchone()
        return row is not None

    def get_node_value(self, content_hash: str) -> Any:
        """Public read of a node by content hash (sync needs this when serving)."""
        return self._load_node(content_hash)

    def export_state_index(
        self, state_hash: str
    ) -> List[Tuple[str, str, vc.VClock]]:
        """Return the full (stable_id, content_hash, vclock) index for a state."""
        import json
        row = self._conn.execute(
            "SELECT index_json FROM states WHERE state_hash=?", (state_hash,)
        ).fetchone()
        if row is None:
            raise NotFound(f"state {state_hash} not in store")
        return [(sid, ch, dict(vclock)) for sid, ch, vclock in json.loads(row[0])]

    def apply_remote_node(self, value: Any) -> str:
        """Insert a node received from a peer; returns its content hash.

        Mirrors `_store_node` but is part of the public sync surface.
        """
        with self._lock, self._conn:
            return self._store_node(value)

    def _install_remote_state(
        self,
        state_hash: str,
        index: List[Tuple[str, str, vc.VClock]],
    ) -> State:
        """Install a peer's state directly (entities + state row + history).

        All node blobs referenced by `index` must already be present locally
        (via `apply_remote_node`). We verify that the supplied `state_hash`
        actually matches the canonical hash of the index, refusing the install
        on mismatch — the caller will have computed it the same way we do.
        """
        import json
        computed = self._compute_state_hash(index)
        if computed != state_hash:
            raise StoreError(
                f"remote state hash mismatch: claimed={state_hash} computed={computed}"
            )
        with self._lock, self._conn:
            for sid, ch, _vclock in index:
                if not self.has_node(ch):
                    raise StoreError(
                        f"cannot install remote state: missing node {ch} for {sid}"
                    )
            existing = self._conn.execute(
                "SELECT seq FROM states WHERE state_hash=?", (state_hash,)
            ).fetchone()
            if existing is not None:
                # Already installed (idempotent). Still rewrite entities so the
                # caller's view at HEAD matches the remote state.
                seq = existing[0]
            else:
                seq_row = self._conn.execute(
                    "SELECT COALESCE(MAX(seq), -1) FROM states"
                ).fetchone()
                seq = (seq_row[0] if seq_row else -1) + 1
                index_json = json.dumps(
                    [[sid, ch, sorted(vclock.items())] for sid, ch, vclock in index],
                    separators=(",", ":"),
                )
                parent = self._current_state_hash()
                self._conn.execute(
                    "INSERT INTO states(state_hash, parent_hash, index_json, "
                    "created_at, created_by, seq) VALUES(?, ?, ?, ?, ?, ?)",
                    (state_hash, parent, index_json, time.time(), self.agent_id, seq),
                )
                for sid, ch, vclock in index:
                    self._conn.execute(
                        "INSERT OR REPLACE INTO entity_history(stable_id, "
                        "state_hash, content_hash, vclock_json) VALUES(?, ?, ?, ?)",
                        (sid, state_hash, ch, json.dumps(vclock)),
                    )
            now = time.time()
            self._conn.execute("DELETE FROM entities")
            for sid, ch, vclock in index:
                self._conn.execute(
                    "INSERT INTO entities(stable_id, current_hash, vclock_json, "
                    "updated_at) VALUES(?, ?, ?, ?)",
                    (sid, ch, json.dumps(vclock), now),
                )
            return State(hash=state_hash, parent=None, seq=seq)


# --- helpers -----------------------------------------------------------------


def _apply_changes(value: Any, changes: Dict[str, Any]) -> Any:
    """Apply dotted-path changes to a (deep-copied) value. Returns new value."""
    import copy
    out = copy.deepcopy(value)
    for path, new in changes.items():
        if not isinstance(out, dict):
            raise StoreError("patch root must be a dict")
        _set_path(out, path.split("."), new)
    return out


def _set_path(d: Any, parts: List[str], new: Any) -> None:
    head, *rest = parts
    if not rest:
        if new is _DELETE:
            d.pop(head, None)
        else:
            d[head] = new
        return
    if head not in d or not isinstance(d[head], dict):
        d[head] = {}
    _set_path(d[head], rest, new)


def _resolve_path(value: Any, path: str) -> Any:
    cur = value
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise StoreError(f"path {path!r} not found")
        cur = cur[part]
    return cur
