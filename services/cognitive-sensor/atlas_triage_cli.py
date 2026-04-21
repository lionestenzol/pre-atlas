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

# Ensure the folder is importable regardless of where `at` is invoked from.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


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


HELP_TEXT = """\
atl - Atlas Triage CLI

THE LOOP
  1. FIND    atl rank --top 20          list highest-value threads
  2. LOOK    atl scan --convo 81        inspect one thread (card + code + quotes)
  3. DECIDE  atl decide 81 MINE --note  record a verdict
  4. HARVEST atl harvest --from-decisions  extract code+quotes to harvest/<id>/
  5. APPLY   atl apply                  push verdicts into results.db

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
    os.chdir(str(HERE))
    # blocking
    rc = subprocess.call(
        [sys.executable, "-m", "http.server", str(port)], cwd=str(HERE))
    return rc


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
