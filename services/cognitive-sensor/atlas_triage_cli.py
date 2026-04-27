"""
atlas_triage_cli.py — single-entry CLI wrapper for the triage pipeline.

Thin dispatcher. Forwards to existing scripts; adds decide/apply/undo/rollback.
Run via `at <subcommand>` (at.cmd wrapper on PATH) or `python atlas_triage_cli.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
DECISIONS = HERE / "thread_decisions.json"
JOURNAL = HERE / "decisions.log"
DB = HERE / "results.db"
AUTO_ACTOR = HERE / "auto_actor.py"
BACKUP_KEEP = 10
VALID_VERDICTS = {"MINE", "KEEP", "CLOSE", "ARCHIVE", "REVIEW", "DROP"}
DELTA_CLOSE_URL = "http://localhost:3001/api/law/close_loop"

# Ensure the folder is importable regardless of where `at` is invoked from.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from aegis_client import log_action as _aegis_log


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ts_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_decisions() -> dict:
    if not DECISIONS.exists():
        return {
            "generated_at": _now_iso(),
            "session": "cli",
            "total_cards": 0,
            "decisions": [],
        }
    return json.loads(DECISIONS.read_text(encoding="utf-8"))


def _save_decisions_atomic(data: dict) -> None:
    data["total_cards"] = len(data.get("decisions", []))
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False,
        dir=str(HERE), prefix=".thread_decisions.", suffix=".tmp"
    )
    try:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, DECISIONS)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def _journal_append(line: str) -> None:
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _forward_to_script(module_name: str, passthrough_args: list[str]) -> int:
    """Import the script and call its main() with a spoofed sys.argv."""
    saved_argv = sys.argv
    try:
        sys.argv = [module_name] + passthrough_args
        mod = __import__(module_name)
        rc = mod.main() if callable(getattr(mod, "main", None)) else 0
        return int(rc or 0)
    finally:
        sys.argv = saved_argv


# ------------------------------ subcommands ------------------------------

def cmd_scan(args, extra):
    return _forward_to_script("thread_scorer", extra)


def cmd_rank(args, extra):
    return _forward_to_script("thread_ranker", extra)


def cmd_themes(args, extra):
    return _forward_to_script("code_themes", extra)


def cmd_winners(args, extra):
    return _forward_to_script("theme_winners", extra)


def cmd_ideas(args, extra):
    return _forward_to_script("idea_code_join", extra)


def cmd_harvest(args, extra):
    return _forward_to_script("harvester", extra)


def cmd_show(args, extra):
    # `at show 81` -> thread_scorer --convo 81
    passthrough = ["--convo", args.convo_id] + extra
    return _forward_to_script("thread_scorer", passthrough)


def cmd_decide(args, extra):
    verdict = args.verdict.upper()
    if verdict not in VALID_VERDICTS:
        print(f"[decide] invalid verdict '{args.verdict}'. "
              f"Valid: {sorted(VALID_VERDICTS)}", file=sys.stderr)
        return 2

    note = args.note or ""
    convo_id = str(args.convo_id)
    entry = {
        "convo_id": convo_id,
        "verdict": verdict,
        "note": note,
        "decided_at": _now_iso(),
        "title": args.title or "",
    }
    line = f"{entry['decided_at']}\t{convo_id}\t{verdict}\t{json.dumps(note)}"

    if args.dry_run:
        print("[decide --dry-run] would append:")
        print(f"  decisions[]: {json.dumps(entry, ensure_ascii=False)}")
        print(f"  journal:     {line}")
        return 0

    data = _load_decisions()
    decisions = data.setdefault("decisions", [])
    # replace-or-append by convo_id
    existing = next((i for i, d in enumerate(decisions)
                     if str(d.get("convo_id")) == convo_id), None)
    if existing is not None:
        decisions[existing] = entry
        action = "updated"
    else:
        decisions.append(entry)
        action = "appended"

    _save_decisions_atomic(data)
    _journal_append(line)
    _aegis_log("atlas_triage", "route_decision", {
        "event": "triage_decide",
        "convo_id": convo_id,
        "verdict": verdict,
        "title": args.title or "",
        "action": action,
        "note": note,
    })
    print(f"[decide] {action} {convo_id} -> {verdict}  "
          f"(total decisions: {data['total_cards']})")
    return 0


def cmd_undo(args, extra):
    data = _load_decisions()
    decisions = data.get("decisions", [])
    if not decisions:
        print("[undo] nothing to undo")
        return 0

    if args.convo_id:
        target = str(args.convo_id)
        before = len(decisions)
        decisions = [d for d in decisions if str(d.get("convo_id")) != target]
        if len(decisions) == before:
            print(f"[undo] no decision found for convo {target}")
            return 1
        data["decisions"] = decisions
        _save_decisions_atomic(data)
        _journal_append(f"{_now_iso()}\t{target}\tUNDO\t\"undo by convo_id\"")
        print(f"[undo] removed verdict for {target}  "
              f"(total decisions: {data['total_cards']})")
    else:
        popped = decisions.pop()
        _save_decisions_atomic(data)
        _journal_append(f"{_now_iso()}\t{popped.get('convo_id')}\tUNDO\t"
                        f"\"undo latest\"")
        print(f"[undo] removed latest ({popped.get('convo_id')} "
              f"-> {popped.get('verdict')})  "
              f"(total decisions: {data['total_cards']})")
    return 0


def _list_backups() -> list[Path]:
    return sorted(HERE.glob("results.db.bak-*"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def _prune_backups():
    backups = _list_backups()
    for old in backups[BACKUP_KEEP:]:
        try:
            old.unlink()
        except OSError:
            pass


def _backup_db() -> Path:
    stamp = _ts_for_filename()
    dest = HERE / f"results.db.bak-{stamp}"
    shutil.copy2(DB, dest)
    _prune_backups()
    return dest


def cmd_apply(args, extra):
    if not DB.exists():
        print(f"[apply] results.db not found at {DB}", file=sys.stderr)
        return 2
    data = _load_decisions()
    decisions = data.get("decisions", [])
    if not decisions:
        print("[apply] no decisions to apply")
        return 0

    # Dedup in-memory: keep the latest verdict per convo.
    latest: dict[str, dict] = {}
    for d in decisions:
        latest[str(d.get("convo_id"))] = d
    rows = [(cid, d["verdict"], d.get("decided_at") or _now_iso())
            for cid, d in latest.items()]

    if args.dry_run:
        print(f"[apply --dry-run] would write {len(rows)} rows:")
        for r in rows:
            print(f"  {r}")
        return 0

    backup = _backup_db()
    print(f"[apply] backup -> {backup.name}")

    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS loop_decisions "
                    "(convo_id TEXT, decision TEXT, date TEXT)")
        existing = {str(r[0]) for r in cur.execute(
            "SELECT convo_id FROM loop_decisions")}
        new_rows = [r for r in rows if r[0] not in existing]
        cur.executemany(
            "INSERT INTO loop_decisions (convo_id, decision, date) "
            "VALUES (?, ?, ?)", new_rows)
        con.commit()
    finally:
        con.close()

    skipped = len(rows) - len(new_rows)
    print(f"[apply] wrote {len(new_rows)} new rows to loop_decisions "
          f"(skipped {skipped} already present)")
    _aegis_log("atlas_triage", "complete_task", {
        "event": "triage_apply",
        "rows_written": len(new_rows),
        "rows_skipped": skipped,
        "backup": backup.name,
    })

    run_actor: bool | None = None
    if args.yes:
        run_actor = True
    elif args.no_actor:
        run_actor = False
    else:
        try:
            resp = input("Run auto_actor.py now? [y/N]: ").strip().lower()
        except EOFError:
            resp = ""
        run_actor = resp in {"y", "yes"}

    if run_actor:
        if not AUTO_ACTOR.exists():
            print(f"[apply] auto_actor.py not found at {AUTO_ACTOR}",
                  file=sys.stderr)
            return 1
        print(f"[apply] running: python {AUTO_ACTOR.name}")
        rc = subprocess.call([sys.executable, str(AUTO_ACTOR)], cwd=str(HERE))
        print(f"[apply] auto_actor exit code: {rc}")
        return rc
    else:
        print(f"[apply] skipped auto_actor. "
              f"Run manually: python {AUTO_ACTOR.name}")
        return 0


def cmd_rollback(args, extra):
    backups = _list_backups()
    if not backups:
        print("[rollback] no backups found")
        return 1
    if args.list:
        print(f"[rollback] {len(backups)} backup(s) available:")
        for i, b in enumerate(backups):
            ts = datetime.fromtimestamp(b.stat().st_mtime).isoformat(
                timespec="seconds")
            marker = " <- newest" if i == 0 else ""
            print(f"  [{i}] {b.name}  ({ts}){marker}")
        return 0

    target = backups[args.index] if args.index is not None else backups[0]
    print(f"[rollback] restoring {target.name} -> results.db")
    shutil.copy2(target, DB)
    print("[rollback] done")
    return 0


def cmd_log(args, extra):
    if not JOURNAL.exists():
        print("[log] no journal yet")
        return 0
    lines = JOURNAL.read_text(encoding="utf-8").splitlines()
    n = args.tail if args.tail and args.tail > 0 else len(lines)
    for line in lines[-n:]:
        print(line)
    return 0


def cmd_status(args, extra):
    data = _load_decisions()
    decisions = data.get("decisions", [])
    by_verdict: dict[str, int] = {}
    for d in decisions:
        v = d.get("verdict", "?")
        by_verdict[v] = by_verdict.get(v, 0) + 1

    applied = 0
    if DB.exists():
        con = sqlite3.connect(DB)
        try:
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS loop_decisions "
                        "(convo_id TEXT, decision TEXT, date TEXT)")
            applied = cur.execute(
                "SELECT COUNT(*) FROM loop_decisions").fetchone()[0]
        finally:
            con.close()

    journaled = 0
    if JOURNAL.exists():
        journaled = sum(1 for _ in JOURNAL.open("r", encoding="utf-8"))

    backups = _list_backups()

    print("Atlas Triage - Status")
    print(f"  Decisions on file : {len(decisions)}")
    for v, c in sorted(by_verdict.items()):
        print(f"    {v:8s} : {c}")
    print(f"  Applied to DB     : {applied} rows in loop_decisions")
    print(f"  Journal entries   : {journaled}")
    print(f"  Backups kept      : {len(backups)}"
          + (f" (newest: {backups[0].name})" if backups else ""))
    return 0


# ------------------------------ lifecycle commands ------------------------------

def _delta_api_key() -> str:
    key_path = HERE.parent.parent / ".aegis-tenant-key"
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    return ""


def _post_close_loop(payload: dict) -> tuple[bool, str]:
    """POST to delta-kernel close_loop endpoint. Returns (ok, message)."""
    import urllib.request
    import urllib.error
    headers = {"Content-Type": "application/json"}
    api_key = _delta_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        req = urllib.request.Request(
            DELTA_CLOSE_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        return False, f"HTTP {e.code} {body}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def cmd_plan(args, extra):
    import lifecycle
    convo_id = str(args.convo_id)
    ref = lifecycle.find_manifest(convo_id)
    if ref is None:
        print(f"[plan] no harvest for {convo_id}. Run `atl harvest --convo {convo_id}` first.",
              file=sys.stderr)
        return 2
    concepts_path = ref.harvest_dir / "concepts.json"
    if not concepts_path.exists():
        print(f"[plan] missing {concepts_path}. Run parse_conversation.py first.",
              file=sys.stderr)
        return 2

    data = json.loads(concepts_path.read_text(encoding="utf-8"))
    concepts = data.get("concepts", [])

    must: list[dict] = []
    nice: list[dict] = []
    skip: list[dict] = []

    if args.auto_scope:
        for c in concepts:
            kind = c.get("kind")
            hits = c.get("hit_count", 0) or 0
            if kind == "technical" and hits >= 5:
                must.append({"id": c["id"], "label": c.get("label", ""), "signal": c.get("signal", "")})
            elif kind == "technical":
                nice.append({"id": c["id"], "label": c.get("label", ""), "signal": c.get("signal", "")})
            elif kind == "decision":
                must.append({"id": c["id"], "label": c.get("label", ""), "signal": c.get("signal", "")})
            else:
                nice.append({"id": c["id"], "label": c.get("label", ""), "signal": c.get("signal", "")})
        print(f"[plan --auto-scope] draft: {len(must)} MUST · {len(nice)} NICE · {len(skip)} SKIP")
        if not args.yes:
            try:
                resp = input("Accept draft? [Y/n/edit]: ").strip().lower()
            except EOFError:
                resp = ""
            if resp == "n":
                print("[plan] aborted.")
                return 1
            if resp == "edit":
                print("[plan] interactive edit not yet implemented; re-run with --yes to accept or omit --auto-scope for interactive mode.")
                return 1
    else:
        print(f"[plan] {len(concepts)} concepts. For each: type m (MUST), n (NICE), s (SKIP), q (quit)")
        for c in concepts:
            print(f"\n[{c['id']}] ({c.get('kind')}) {c.get('label', '')}")
            if c.get("evidence_quote"):
                print(f"    {c['evidence_quote'][:160]}")
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n[plan] aborted.")
                return 1
            entry = {"id": c["id"], "label": c.get("label", ""), "signal": c.get("signal", "")}
            if choice == "m":
                must.append(entry)
            elif choice == "n":
                nice.append(entry)
            elif choice == "s":
                entry["reason"] = input("    skip reason: ").strip() or "(none)"
                skip.append(entry)
            elif choice == "q":
                print("[plan] quit; nothing written.")
                return 1
            else:
                nice.append(entry)

    plan_doc = {
        "convo_id": convo_id,
        "planned_at": _now_iso(),
        "must": must,
        "nice": nice,
        "skip": skip,
    }
    plan_path = ref.harvest_dir / "build_plan.json"
    plan_path.write_text(json.dumps(plan_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[plan] wrote {plan_path}")

    try:
        lifecycle.transition(convo_id, "PLANNED",
                             updates={"planned_at": _now_iso(),
                                      "plan_counts": {"must": len(must), "nice": len(nice), "skip": len(skip)}})
    except lifecycle.LifecycleError as e:
        print(f"[plan] status transition warning: {e}")
    print(f"[plan] status -> PLANNED  (must={len(must)} nice={len(nice)} skip={len(skip)})")
    return 0


def _suggest_artifact(convo_id: str, decided_at: str | None) -> list[str]:
    """Return up to 3 candidate artifact paths based on recent apps/ dirs."""
    repo_root = HERE.parent.parent
    apps = repo_root / "apps"
    if not apps.exists():
        return []
    candidates = []
    for sub in apps.iterdir():
        if not sub.is_dir():
            continue
        try:
            mtime = sub.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, sub))
    candidates.sort(reverse=True)
    rel = []
    for _, sub in candidates[:5]:
        try:
            rel.append(str(sub.relative_to(repo_root)).replace("\\", "/"))
        except ValueError:
            rel.append(str(sub))
    return rel[:3]


def cmd_start(args, extra):
    import lifecycle
    convo_id = str(args.convo_id)
    ref = lifecycle.find_manifest(convo_id)
    if ref is None:
        print(f"[start] no harvest for {convo_id}.", file=sys.stderr)
        return 2

    artifact = args.artifact_path
    if not artifact or args.suggest:
        suggestions = _suggest_artifact(convo_id, None)
        if suggestions:
            print("[start] artifact candidates (newest first):")
            for i, s in enumerate(suggestions):
                print(f"  [{i}] {s}")
            try:
                choice = input("Pick [0-N], or type a path: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[start] aborted.")
                return 1
            if choice.isdigit() and 0 <= int(choice) < len(suggestions):
                artifact = suggestions[int(choice)]
            elif choice:
                artifact = choice
        if not artifact:
            print("[start] no artifact path given.", file=sys.stderr)
            return 2

    try:
        lifecycle.transition(convo_id, "BUILDING",
                             updates={"artifact_path": artifact,
                                      "building_started_at": _now_iso()},
                             extra_journal=artifact)
    except lifecycle.LifecycleError as e:
        print(f"[start] {e}", file=sys.stderr)
        return 2
    print(f"[start] {convo_id} -> BUILDING  (artifact: {artifact})")
    return 0


def cmd_review(args, extra):
    import lifecycle
    convo_id = str(args.convo_id)
    manifest = lifecycle.load_manifest(convo_id)
    if manifest is None:
        print(f"[review] no harvest for {convo_id}.", file=sys.stderr)
        return 2
    artifact = manifest.get("artifact_path")
    if not artifact:
        print(f"[review] no artifact_path on manifest. Run `atl start {convo_id} <path>` first.",
              file=sys.stderr)
        return 2

    import verify_coverage
    j, _m = verify_coverage.verify(
        int(convo_id),
        Path(artifact),
        auto=args.auto,
        use_plan=not args.no_plan,
    )
    coverage_doc = json.loads(Path(j).read_text(encoding="utf-8"))
    ref = lifecycle.find_manifest(convo_id)
    plan_path = ref.harvest_dir / "build_plan.json" if ref else None
    plan_doc = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path and plan_path.exists() else None

    s = coverage_doc.get("summary", {})
    good = s.get("covered", 0) + s.get("partial", 0)
    total = max(1, good + s.get("missing", 0) + s.get("unverifiable", 0))
    score = round(good / total, 3)

    passed, reason = lifecycle.coverage_gate(coverage_doc, plan_doc)

    try:
        lifecycle.transition(convo_id, "REVIEWING",
                             updates={"reviewed_at": _now_iso(),
                                      "coverage_score": score,
                                      "coverage_gate_passed": passed})
    except lifecycle.LifecycleError as e:
        print(f"[review] {e}", file=sys.stderr)
        return 2

    print(f"\n[review] coverage: covered={s.get('covered', 0)} "
          f"partial={s.get('partial', 0)} missing={s.get('missing', 0)} "
          f"unverifiable={s.get('unverifiable', 0)}")
    print(f"[review] score: {score}  gate: {'PASS' if passed else 'BLOCKED'}  ({reason})")
    return 0 if passed else 1


def cmd_done(args, extra):
    import lifecycle
    convo_id = str(args.convo_id)
    manifest = lifecycle.load_manifest(convo_id)
    if manifest is None:
        print(f"[done] no harvest for {convo_id}.", file=sys.stderr)
        return 2
    if manifest.get("status") != "REVIEWING":
        print(f"[done] status must be REVIEWING; currently {manifest.get('status')}.",
              file=sys.stderr)
        return 2
    if not manifest.get("coverage_gate_passed") and not args.force:
        print(f"[done] coverage gate did not pass. Re-run `atl review {convo_id}` or use --force.",
              file=sys.stderr)
        return 1

    updates = {"done_at": _now_iso()}
    try:
        lifecycle.transition(convo_id, "DONE", updates=updates, force=args.force)
    except lifecycle.LifecycleError as e:
        print(f"[done] {e}", file=sys.stderr)
        return 2

    payload = {
        "loop_id": convo_id,
        "title": manifest.get("title", ""),
        "outcome": "closed",
        "artifact_path": manifest.get("artifact_path"),
        "coverage_score": manifest.get("coverage_score"),
        "status": "DONE",
    }
    ok, msg = _post_close_loop(payload)
    print(f"[done] {convo_id} -> DONE  delta-kernel: {msg}")
    if not ok and not args.force:
        print("[done] NOTE: delta-kernel POST failed. Manifest is DONE locally.")
    return 0


def _resolve_or_drop(convo_id: str, target: str, outcome: str) -> int:
    import lifecycle
    manifest = lifecycle.load_manifest(convo_id)
    title = manifest.get("title", "") if manifest else ""
    try:
        if manifest is not None:
            lifecycle.transition(convo_id, target, updates={"done_at": _now_iso()})
        else:
            print(f"[{target.lower()}] no harvest found; skipping manifest update (loop-only close).")
    except lifecycle.LifecycleError as e:
        print(f"[{target.lower()}] {e}", file=sys.stderr)
        return 2
    payload = {
        "loop_id": convo_id,
        "title": title,
        "outcome": outcome,
        "artifact_path": None,
        "coverage_score": None,
        "status": target,
    }
    ok, msg = _post_close_loop(payload)
    print(f"[{target.lower()}] {convo_id} -> {target}  delta-kernel: {msg}")
    return 0 if ok else 1


def cmd_resolve(args, extra):
    return _resolve_or_drop(str(args.convo_id), "RESOLVED", "closed")


def cmd_drop(args, extra):
    return _resolve_or_drop(str(args.convo_id), "DROPPED", "archived")


def cmd_lifecycle_status(args, extra):
    import lifecycle
    convo_id = str(args.convo_id)
    manifest = lifecycle.load_manifest(convo_id)
    if manifest is None:
        print(f"{convo_id}: no manifest")
        print(f"  next: {lifecycle.next_command(None)}")
        return 1
    status = manifest.get("status", "HARVESTED")
    print(f"{convo_id}: {status}")
    print(f"  verdict:       {manifest.get('verdict')}")
    print(f"  harvested_at:  {manifest.get('harvested_at')}")
    if manifest.get("artifact_path"):
        print(f"  artifact:      {manifest['artifact_path']}")
    if manifest.get("coverage_score") is not None:
        print(f"  coverage:      {manifest['coverage_score']}  "
              f"gate: {'PASS' if manifest.get('coverage_gate_passed') else 'BLOCKED'}")
    if manifest.get("done_at"):
        print(f"  done_at:       {manifest['done_at']}")
    print(f"  next:          {lifecycle.next_command(status)}")
    return 0


def cmd_in_progress(args, extra):
    import lifecycle
    rows = lifecycle.list_by_status({"PLANNED", "BUILDING", "REVIEWING"})
    if not rows:
        print("[in-progress] no threads in flight.")
        return 0
    print(f"[in-progress] {len(rows)} thread(s):")
    print(f"  {'ID':>6}  {'STATUS':<10}  {'VERDICT':<8}  TITLE")
    print(f"  {'-'*6}  {'-'*10}  {'-'*8}  {'-'*40}")
    for r in rows:
        title = (r.get("title") or "")[:50]
        print(f"  {r.get('convo_id', '?'):>6}  {r.get('status', '?'):<10}  "
              f"{r.get('verdict', '?'):<8}  {title}")
    return 0


HELP_TEXT = """\
atl - Atlas Triage CLI

THE LOOP
  1. FIND    atl rank --top 20          list highest-value threads
  2. LOOK    atl scan --convo 81        inspect one thread (card + code + quotes)
  3. DECIDE  atl decide 81 MINE --note  record a verdict
  4. HARVEST atl harvest --from-decisions  extract code+quotes to harvest/<id>/
  5. APPLY   atl apply                  push verdicts into results.db
  6. PLAN    atl plan 81 --auto-scope   scope concepts -> build_plan.json
  7. START   atl start 81 apps/foo      link artifact, status -> BUILDING
  8. REVIEW  atl review 81              verify coverage, status -> REVIEWING
  9. DONE    atl done 81                gate + close, status -> DONE
  - or -    atl resolve 81             CLOSE verdict terminal (no artifact)
  - or -    atl drop 81                ARCHIVE verdict terminal (no artifact)

VERDICTS
  MINE     extract code/ideas into a repo
  KEEP     valuable reference, leave intact
  CLOSE    resolved, stop touching it
  ARCHIVE  old but worth storing
  REVIEW   come back later
  DROP     garbage, ignore

READ (display only)
  atl rank   [--top N] [--min-blocks N]  ranked table across all threads
  atl scan   --convo <id> | --cluster N  per-thread card
  atl show   <id>                        alias for scan --convo <id>
  atl themes [--theme X] [--limit N]     24 project themes across code blocks
  atl winners                            best thread per theme
  atl ideas  [--top N] [--id X]          canonical ideas + code signals
  atl log    [--tail N]                  journal of every decide/undo
  atl status                             verdict counts, applied rows, backups

WRITE (mutates files)
  atl decide <id> <VERDICT> [--note "..."] [--dry-run]
  atl undo   [<id>]                      pop latest or by convo_id
  atl harvest --convo <id> | --from-decisions
  atl apply  [--yes] [--no-actor] [--dry-run]
  atl rollback [--list] [--index N]      restore results.db from backup

LIFECYCLE (per-thread status in harvest/<id>/manifest.json)
  atl plan <id> [--auto-scope] [--yes]   concepts -> MUST/NICE/SKIP -> build_plan.json
  atl start <id> [<path>] [--suggest]    set artifact_path; status BUILDING
  atl review <id> [--auto] [--no-plan]   run verify_coverage; status REVIEWING
  atl done <id> [--force]                gate check + POST close_loop; status DONE
  atl resolve <id>                       CLOSE verdict -> RESOLVED
  atl drop <id>                          ARCHIVE verdict -> DROPPED
  atl lifecycle <id>                     show status + next command
  atl in-progress                        list PLANNED/BUILDING/REVIEWING

SERVE
  atl serve  [--port 8765]               boot http server + open thread_cards.html

SAFETY
  - Every `decide` writes to decisions.log (append-only, never rewritten)
  - Every `apply` copies results.db to results.db.bak-<timestamp> first
  - `undo` pops decisions; journal retains the history
  - `rollback` restores the most recent backup (or --index N for older)
  - `--dry-run` on decide/apply shows what would happen, writes nothing

TYPICAL SESSION
  atl status                              see where you are
  atl rank --top 20                       pick threads to look at
  atl scan --convo 81                     deep-read the top one
  atl decide 81 MINE --note "port exec"   lock verdict
  atl harvest --from-decisions            extract everything decided
  atl apply                               write to DB (prompts y/N for auto_actor)

TIPS
  - In PowerShell/cmd: `atl <cmd>` works bare
  - In Git Bash:       type `atl.cmd <cmd>` (shell ignores PATHEXT)
  - Pass `--help` to any subcommand's underlying script for its flags:
       atl scan --help, atl rank --help, atl harvest --help
"""


def cmd_help(args, extra):
    print(HELP_TEXT)
    return 0


def cmd_serve(args, extra):
    port = args.port
    url = f"http://localhost:{port}/thread_cards.html"
    print(f"[serve] http://localhost:{port}/  (Ctrl+C to stop)")
    print(f"[serve] opening {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    # Use triage_server — file serving + live /api/decide endpoint
    os.chdir(str(HERE))
    from triage_server import serve as triage_serve
    return triage_serve(port)


# ------------------------------ parser ------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="atl", description="Atlas triage CLI. Run `atl help` for the guide.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("help", help="show the full guide with examples")
    sp.set_defaults(func=cmd_help)

    # pass-through commands: we swallow remaining args as "extra"
    for name in ("scan", "rank", "themes", "winners", "ideas", "harvest"):
        sp = sub.add_parser(name, add_help=False,
                            help=f"forward to {name} script (use --help on script)")
        sp.set_defaults(func=globals()[f"cmd_{name}"])

    sp = sub.add_parser("show", help="pretty-print a thread card")
    sp.add_argument("convo_id")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("decide", help="record a verdict for a convo")
    sp.add_argument("convo_id")
    sp.add_argument("verdict", help=f"one of {sorted(VALID_VERDICTS)}")
    sp.add_argument("--note", default="")
    sp.add_argument("--title", default="")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_decide)

    sp = sub.add_parser("undo", help="remove latest or specific verdict")
    sp.add_argument("convo_id", nargs="?")
    sp.set_defaults(func=cmd_undo)

    sp = sub.add_parser("apply",
                        help="write decisions to loop_decisions in results.db")
    grp = sp.add_mutually_exclusive_group()
    grp.add_argument("--yes", action="store_true",
                     help="skip prompt and run auto_actor.py")
    grp.add_argument("--no-actor", action="store_true",
                     help="skip prompt, do not run auto_actor.py")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_apply)

    sp = sub.add_parser("rollback", help="restore results.db from backup")
    sp.add_argument("--list", action="store_true")
    sp.add_argument("--index", type=int,
                    help="pick backup by index from --list (0=newest)")
    sp.set_defaults(func=cmd_rollback)

    sp = sub.add_parser("log", help="show decision journal")
    sp.add_argument("--tail", type=int, default=20)
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("status", help="decision and apply counts")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("serve", help="boot http server for thread_cards.html")
    sp.add_argument("--port", type=int, default=8765)
    sp.set_defaults(func=cmd_serve)

    # Lifecycle commands
    sp = sub.add_parser("plan", help="scope concepts into build_plan.json")
    sp.add_argument("convo_id")
    sp.add_argument("--auto-scope", action="store_true",
                    help="auto-classify concepts (high hit -> MUST, rest -> NICE)")
    sp.add_argument("--yes", action="store_true",
                    help="accept draft without prompting (with --auto-scope)")
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("start", help="link artifact path; status -> BUILDING")
    sp.add_argument("convo_id")
    sp.add_argument("artifact_path", nargs="?", default="")
    sp.add_argument("--suggest", action="store_true",
                    help="show candidate paths from apps/ even if one was provided")
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("review", help="run verify_coverage; status -> REVIEWING")
    sp.add_argument("convo_id")
    sp.add_argument("--auto", action="store_true",
                    help="use claude -p for idea/decision concepts")
    sp.add_argument("--no-plan", action="store_true",
                    help="verify against all concepts, not just MUST+NICE")
    sp.set_defaults(func=cmd_review)

    sp = sub.add_parser("done", help="close loop with artifact link; status -> DONE")
    sp.add_argument("convo_id")
    sp.add_argument("--force", action="store_true",
                    help="bypass coverage gate")
    sp.set_defaults(func=cmd_done)

    sp = sub.add_parser("resolve", help="CLOSE verdict terminal -> RESOLVED")
    sp.add_argument("convo_id")
    sp.set_defaults(func=cmd_resolve)

    sp = sub.add_parser("drop", help="ARCHIVE verdict terminal -> DROPPED")
    sp.add_argument("convo_id")
    sp.set_defaults(func=cmd_drop)

    sp = sub.add_parser("lifecycle", help="show current status + next command")
    sp.add_argument("convo_id")
    sp.set_defaults(func=cmd_lifecycle_status)

    sp = sub.add_parser("in-progress", help="list threads in PLANNED/BUILDING/REVIEWING")
    sp.set_defaults(func=cmd_in_progress)

    # fuzz — anatomy extension corpus generator (Part A of the training harness)
    from fuzz.cli import register as register_fuzz
    register_fuzz(sub)

    return p


PASSTHROUGH = {"scan", "rank", "themes", "winners", "ideas", "harvest"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in PASSTHROUGH:
        cmd = argv[0]
        extra = argv[1:]
        func = globals()[f"cmd_{cmd}"]
        return func(argparse.Namespace(cmd=cmd), extra)

    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args, []) or 0


if __name__ == "__main__":
    sys.exit(main())
