"""
lifecycle.py — thread status state machine.

One thread lives in one of these statuses:

  HARVESTED  →  PLANNED  →  BUILDING  →  REVIEWING  →  DONE     (MINE path)
                                                   →  RESOLVED  (CLOSE path)
                                                   →  DROPPED   (ARCHIVE path)

Status is stored in harvest/<id>_<slug>/manifest.json. thread_decisions.json
mirrors it. decisions.log gets an append-only STATUS line per transition.

Verdict (MINE/KEEP/CLOSE/ARCHIVE/REVIEW/DROP) is a separate axis — what the
thread is. Status is how far through its lifecycle it has moved.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

BASE = Path(__file__).parent.resolve()
HARVEST_ROOT = BASE / "harvest"
DECISIONS_PATH = BASE / "thread_decisions.json"
JOURNAL_PATH = BASE / "decisions.log"

STATUSES = (
    "HARVESTED",
    "PLANNED",
    "BUILDING",
    "REVIEWING",
    "DONE",
    "RESOLVED",
    "DROPPED",
)
TERMINAL = {"DONE", "RESOLVED", "DROPPED"}
MID_LIFECYCLE = {"PLANNED", "BUILDING", "REVIEWING"}

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "HARVESTED": frozenset({"PLANNED", "RESOLVED", "DROPPED"}),
    "PLANNED": frozenset({"BUILDING", "RESOLVED", "DROPPED"}),
    "BUILDING": frozenset({"REVIEWING", "DROPPED"}),
    "REVIEWING": frozenset({"DONE", "BUILDING", "DROPPED"}),
    "DONE": frozenset(),
    "RESOLVED": frozenset(),
    "DROPPED": frozenset(),
}

COVERAGE_THRESHOLD = 0.8

logger = logging.getLogger(__name__)


class LifecycleError(Exception):
    """Raised when a status transition is not permitted."""


@dataclass(frozen=True)
class ManifestRef:
    convo_id: str
    harvest_dir: Path
    manifest_path: Path


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def find_manifest(convo_id: str) -> ManifestRef | None:
    """Locate harvest/<id>_<slug>/manifest.json. Returns None if absent."""
    convo_id = str(convo_id)
    if not HARVEST_ROOT.exists():
        return None
    matches = sorted(HARVEST_ROOT.glob(f"{convo_id}_*"))
    if not matches:
        exact = HARVEST_ROOT / convo_id
        if exact.exists():
            matches = [exact]
    for d in matches:
        manifest = d / "manifest.json"
        if manifest.exists():
            return ManifestRef(convo_id=convo_id, harvest_dir=d, manifest_path=manifest)
    return None


def load_manifest(convo_id: str) -> dict | None:
    ref = find_manifest(convo_id)
    if ref is None:
        return None
    return json.loads(ref.manifest_path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def write_manifest(ref: ManifestRef, data: dict) -> None:
    _atomic_write_json(ref.manifest_path, data)


def get_status(convo_id: str) -> str | None:
    data = load_manifest(convo_id)
    if data is None:
        return None
    return data.get("status")


def journal_status(convo_id: str, new_status: str, extra: str = "") -> None:
    line = f"{_now_iso()}\t{convo_id}\tSTATUS\t{new_status}\t{extra}"
    with JOURNAL_PATH.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _sync_decisions(convo_id: str, new_status: str) -> None:
    """Mirror status onto the matching entry in thread_decisions.json."""
    if not DECISIONS_PATH.exists():
        return
    try:
        data = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("thread_decisions.json is malformed; skipping status sync")
        return
    changed = False
    for entry in data.get("decisions", []):
        if str(entry.get("convo_id")) == str(convo_id):
            if entry.get("status") != new_status:
                entry["status"] = new_status
                entry["status_updated_at"] = _now_iso()
                changed = True
            break
    if changed:
        _atomic_write_json(DECISIONS_PATH, data)


def assert_transition(current: str | None, target: str) -> None:
    # Legacy manifests created before the lifecycle existed have no status field.
    # Treat them as HARVESTED — they've been harvested, they just haven't been
    # explicitly migrated yet. `atl plan` and friends should work without
    # requiring a separate migration step.
    effective = current or "HARVESTED"
    if target not in STATUSES:
        raise LifecycleError(f"unknown status {target!r}")
    allowed = ALLOWED_TRANSITIONS.get(effective, frozenset())
    if target not in allowed:
        raise LifecycleError(
            f"illegal transition {effective} -> {target}. "
            f"Allowed from {effective}: {sorted(allowed) or 'none (terminal)'}"
        )


def transition(
    convo_id: str,
    target: str,
    *,
    updates: dict | None = None,
    extra_journal: str = "",
    force: bool = False,
) -> dict:
    """Move a thread to `target`. Returns the updated manifest dict."""
    ref = find_manifest(convo_id)
    if ref is None:
        raise LifecycleError(
            f"no manifest found for convo {convo_id}. Run `atl harvest {convo_id}` first."
        )
    data = json.loads(ref.manifest_path.read_text(encoding="utf-8"))
    current = data.get("status")
    if not force:
        assert_transition(current, target)
    data["status"] = target
    data.setdefault("status_history", []).append(
        {"from": current, "to": target, "at": _now_iso()}
    )
    if updates:
        data.update(updates)
    write_manifest(ref, data)
    journal_status(convo_id, target, extra_journal + (" [forced]" if force and current not in ALLOWED_TRANSITIONS.get(current or "", frozenset()) else ""))
    _sync_decisions(convo_id, target)
    return data


def list_by_status(statuses: Iterable[str]) -> list[dict]:
    """Return every manifest whose status is in `statuses`."""
    wanted = set(statuses)
    out: list[dict] = []
    if not HARVEST_ROOT.exists():
        return out
    for sub in sorted(HARVEST_ROOT.iterdir()):
        if not sub.is_dir():
            continue
        manifest = sub / "manifest.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("status") in wanted:
            out.append(data)
    return out


def next_command(status: str | None) -> str:
    return {
        None: "atl harvest --convo <id>",
        "HARVESTED": "atl plan <id>",
        "PLANNED": "atl start <id> [artifact_path]",
        "BUILDING": "atl review <id>",
        "REVIEWING": "atl done <id>",
        "DONE": "(terminal — nothing to do)",
        "RESOLVED": "(terminal — nothing to do)",
        "DROPPED": "(terminal — nothing to do)",
    }.get(status, "(unknown status)")


def coverage_gate(coverage_doc: dict, plan_doc: dict | None) -> tuple[bool, str]:
    """Evaluate whether coverage passes the done gate.

    Gate: zero MUST items missing, AND (covered + partial) / (must+nice) >= 0.8.
    If no plan is provided, fall back to overall covered/partial >= threshold.
    """
    rows = coverage_doc.get("rows", [])
    by_id = {r["id"]: r for r in rows}

    if plan_doc:
        must_ids = [i["id"] for i in plan_doc.get("must", [])]
        nice_ids = [i["id"] for i in plan_doc.get("nice", [])]
        scoped = must_ids + nice_ids
        missing_musts = [mid for mid in must_ids if by_id.get(mid, {}).get("status") == "missing"]
        if missing_musts:
            return False, f"{len(missing_musts)} MUST item(s) missing: {', '.join(missing_musts)}"
        scored = [by_id[i] for i in scoped if i in by_id]
        if not scored:
            return False, "no scoped concepts to score"
        good = sum(1 for r in scored if r["status"] in ("covered", "partial"))
        ratio = good / len(scored)
    else:
        if not rows:
            return False, "no coverage rows"
        good = sum(1 for r in rows if r["status"] in ("covered", "partial"))
        ratio = good / len(rows)

    if ratio + 1e-9 < COVERAGE_THRESHOLD:
        return False, f"coverage {ratio:.2f} below threshold {COVERAGE_THRESHOLD}"
    return True, f"coverage {ratio:.2f} (threshold {COVERAGE_THRESHOLD})"
