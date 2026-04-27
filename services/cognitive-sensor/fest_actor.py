"""Close fest task loops from thread_decisions.

Reads thread_decisions.json, finds source:"fest" cards with terminal
verdicts (DONE / SKIP), and:

  1. Marks the task complete via `fest task completed <relpath> --json`
     inside the festival directory in WSL.
  2. If the festival has a `.atlas-link.json` config, mirrors the
     completion to delta-kernel's goal criteria so the Atlas 90-day
     commitment progress bar moves automatically.

Mirror config shape (`.atlas-link.json` at festival root, optional):

    {
      "goal_id": "g-moake7hk-canvas-product-90-day-commitment",
      "mode": "phase_to_criterion",
      "phase_to_criterion": {
        "001_C1_DEMO_VIDEO": "c1",
        "002_C2_BRAND": "c2",
        ...
      }
    }

Mode "phase_to_criterion" closes an Atlas criterion when every task in
the phase is done. Mode "task_to_criterion" would close one criterion
per task (not used yet).

Dry-run by default. Set FEST_ACTOR_APPLY=1 to actually call the fest CLI
and hit delta-kernel. Run as Phase 4.8 of run_daily.py after fs_actor.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
DECISIONS_PATH = BASE / "thread_decisions.json"
CARDS_PATH = BASE / "thread_cards.json"
LOG_PATH = BASE / "fest_actor_log.json"

TERMINAL_VERDICTS = {"DONE", "SKIP"}
APPLY = os.environ.get("FEST_ACTOR_APPLY") == "1"
DELTA_URL = os.environ.get("DELTA_KERNEL_URL", "http://127.0.0.1:3001")
TENANT_KEY_FILE = BASE.parent.parent / ".aegis-tenant-key"


@dataclass(frozen=True)
class FestCardRef:
    convo_id: str
    festival_id: str
    festival_name: str
    lifecycle: str
    phase: str
    sequence: str
    task_num: str
    task_path: str

    @property
    def festival_root(self) -> str:
        # task_path: /root/festival-project/festivals/<lc>/<fest>/<phase>/<seq>/<file>.md
        # festival root = everything up to and including <fest>.
        idx = self.task_path.find(f"/{self.festival_name}/")
        if idx < 0:
            return ""
        return self.task_path[: idx + len(self.festival_name) + 1]

    @property
    def relative_task_path(self) -> str:
        root = self.festival_root
        if not root:
            return ""
        return self.task_path[len(root):].lstrip("/")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _fest_card_index() -> dict[str, FestCardRef]:
    doc = _load_json(CARDS_PATH)
    out: dict[str, FestCardRef] = {}
    for c in doc.get("cards", []):
        if c.get("source") != "fest":
            continue
        out[str(c.get("convo_id"))] = FestCardRef(
            convo_id=str(c.get("convo_id")),
            festival_id=str(c.get("festival_id", "")),
            festival_name=str(c.get("festival_name", "")),
            lifecycle=str(c.get("lifecycle", "")),
            phase=str(c.get("phase", "")),
            sequence=str(c.get("sequence", "")),
            task_num=str(c.get("task_num", "")),
            task_path=str(c.get("task_path", "")),
        )
    return out


def _pending_decisions(index: dict[str, FestCardRef], processed: set[str]) -> list[dict]:
    dec_doc = _load_json(DECISIONS_PATH)
    out: list[dict] = []
    for d in dec_doc.get("decisions", []):
        cid = str(d.get("convo_id"))
        if cid not in index:
            continue
        verdict = str(d.get("verdict", "")).upper()
        if verdict not in TERMINAL_VERDICTS:
            continue
        key = f"{cid}|{d.get('decided_at', '')}"
        if key in processed:
            continue
        out.append({"cid": cid, "verdict": verdict, "decided_at": d.get("decided_at", ""), "note": d.get("note", "")})
    return out


def _run_fest_task_completed(ref: FestCardRef) -> dict:
    """Mark the task complete via `fest task completed`.

    `--json` is rejected by fest when a task has no recorded outcome yet;
    interactive confirmation is the only way. We pipe `y` through and
    parse exit code + stdout. Quality gates (unfilled markers etc.) can
    still block the completion and produce a non-zero return code, which
    surfaces as `ok: False` in the log.
    """
    root = ref.festival_root
    rel = ref.relative_task_path
    if not root or not rel:
        return {"ok": False, "reason": "cannot_resolve_paths"}
    shell_cmd = f"cd {shell_quote(root)} && printf 'y\\n' | fest task completed {shell_quote(rel)}"
    if not APPLY:
        return {"ok": True, "dry_run": True, "command": shell_cmd}
    cmd = ["wsl", "-d", "Ubuntu", "--", "bash", "-c", shell_cmd]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": f"subprocess_error:{exc}"}
    tail = proc.stdout[-500:] if proc.stdout else ""
    return {
        "ok": proc.returncode == 0,
        "rc": proc.returncode,
        "stdout_tail": tail,
        "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
    }


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _read_atlas_link(festival_root: str) -> dict | None:
    if not festival_root:
        return None
    # festival_root is a WSL path. Convert to UNC for Windows read.
    unc = festival_root.replace("/root/", "//wsl.localhost/Ubuntu/root/")
    p = Path(unc) / ".atlas-link.json"
    if not p.exists():
        # Try wsl cat fallback for paths that UNC can't resolve on this host.
        try:
            proc = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "cat", f"{festival_root}/.atlas-link.json"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return None
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _tenant_key() -> str:
    try:
        return TENANT_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _atlas_criterion_done(goal_id: str, criterion_id: str) -> dict:
    if not APPLY:
        return {"ok": True, "dry_run": True,
                "endpoint": f"POST {DELTA_URL}/api/goals/{goal_id}/criteria/{criterion_id}/done"}
    key = _tenant_key()
    if not key:
        return {"ok": False, "reason": "no_tenant_key"}
    req = urllib.request.Request(
        f"{DELTA_URL}/api/goals/{goal_id}/criteria/{criterion_id}/done",
        data=b"{}",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return {"ok": True, "status": resp.status, "body": body[:300]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode("utf-8", errors="replace")[:300]}
    except urllib.error.URLError as e:
        return {"ok": False, "reason": f"url_error:{e}"}


def _phase_all_done(festival_root: str, phase: str) -> bool:
    """Return True if every task in the phase has status != pending."""
    if not APPLY:
        # In dry-run we can't be sure; assume False so we log the intent but
        # don't falsely claim a phase is complete.
        return False
    cmd = ["wsl", "-d", "Ubuntu", "--", "bash", "-c",
           f"cd {shell_quote(festival_root)} && fest progress --json 2>/dev/null || fest status --json 2>/dev/null"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False
    # Walk the tree looking for the phase entry; shape varies by fest
    # version so accept any dict with `phases` / `sequences` / `tasks`.
    phases = data.get("phases") or data.get("phase_status") or []
    if isinstance(phases, dict):
        phases = list(phases.values())
    for p in phases:
        if not isinstance(p, dict):
            continue
        pid = p.get("id") or p.get("name") or ""
        if pid != phase:
            continue
        tasks = []
        for seq in (p.get("sequences") or []):
            tasks.extend(seq.get("tasks") or [])
        tasks.extend(p.get("tasks") or [])
        if not tasks:
            return False
        return all(t.get("status") not in ("pending", None, "") for t in tasks)
    return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    index = _fest_card_index()
    log = _load_json(LOG_PATH) or {"runs": []}
    # A decision is "processed" only after a successful apply. Dry runs
    # and failed applies (quality gate rejection, missing fest CLI, etc.)
    # stay queued so the next run can retry.
    processed: set[str] = set()
    for run in log.get("runs", []):
        if not run.get("applied"):
            continue
        for item in run.get("items", []):
            if item.get("fest", {}).get("ok"):
                processed.add(item.get("key", ""))

    pending = _pending_decisions(index, processed)
    items: list[dict] = []

    print("\n=== FEST ACTOR ===")
    print(f"  APPLY={APPLY}  pending={len(pending)}")

    for d in pending:
        ref = index[d["cid"]]
        fest_res = _run_fest_task_completed(ref) if d["verdict"] == "DONE" else {"ok": True, "skipped": True}
        atlas_res: dict | None = None

        if d["verdict"] == "DONE":
            link = _read_atlas_link(ref.festival_root)
            if link and link.get("mode") == "phase_to_criterion":
                cid = link.get("phase_to_criterion", {}).get(ref.phase)
                goal_id = link.get("goal_id", "")
                if cid and goal_id and _phase_all_done(ref.festival_root, ref.phase):
                    atlas_res = _atlas_criterion_done(goal_id, cid)
                elif cid and goal_id:
                    atlas_res = {"ok": True, "skipped": "phase_not_all_done", "phase": ref.phase, "criterion": cid}

        item = {
            "key": f"{d['cid']}|{d['decided_at']}",
            "convo_id": d["cid"],
            "verdict": d["verdict"],
            "festival_id": ref.festival_id,
            "phase": ref.phase,
            "task_rel": ref.relative_task_path,
            "fest": fest_res,
            "atlas": atlas_res,
        }
        items.append(item)
        fest_ok = "OK" if fest_res.get("ok") else "FAIL"
        atlas_note = ""
        if atlas_res:
            atlas_note = f" atlas={'OK' if atlas_res.get('ok') else 'FAIL'}"
        print(f"  [{fest_ok}] {d['verdict']:<4} {ref.festival_id} {ref.phase}/{ref.sequence}/{ref.task_num}{atlas_note}")

    log.setdefault("runs", []).append({"ran_at": _now(), "applied": APPLY, "items": items})
    atomic_write_json(LOG_PATH, log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
