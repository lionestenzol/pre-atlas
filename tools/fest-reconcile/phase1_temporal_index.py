#!/usr/bin/env python3
"""Phase 1 - Temporal index per channel.

Produces three JSONs that subsequent phases join on:
  - festival_out/chatgpt_temporal.json (6534 convos -> dates + title)
  - festival_out/cc_temporal.json      (1017 sessions -> dates + project_dir + first user msg)
  - festival_out/fs_temporal.json      (140 portfolio paths -> mtime/ctime)

Run subcommand-style:
  python phase1_temporal_index.py chatgpt
  python phase1_temporal_index.py cc
  python phase1_temporal_index.py fs
  python phase1_temporal_index.py all
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "tools" / "fest-reconcile" / "festival_out"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def write_out(name: str, payload: dict) -> Path:
    path = OUT_DIR / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def chatgpt_temporal() -> None:
    db = REPO / "services" / "cognitive-sensor" / "results.db"
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute(
        """
        SELECT t.convo_id, MIN(t.date), MAX(t.date), c.title
        FROM convo_time t
        LEFT JOIN convo_titles c ON c.convo_id = t.convo_id
        GROUP BY t.convo_id
        ORDER BY MIN(t.date)
        """
    )
    items: list[dict] = []
    for cid, dmin, dmax, title in cur.fetchall():
        items.append({
            "convo_id": cid,
            "first_date": dmin,
            "last_date": dmax,
            "title": title or "",
        })
    con.close()
    out = {
        "generated_at": datetime.now().isoformat(),
        "source": str(db),
        "schema": "convo_id -> (first_date, last_date, title)",
        "date_range": [items[0]["first_date"] if items else None,
                       items[-1]["first_date"] if items else None],
        "count": len(items),
        "items": items,
    }
    p = write_out("chatgpt_temporal.json", out)
    print(f"chatgpt: {len(items):>5} convos  -> {p.name}")


def _extract_first_user_text(content) -> str:
    if isinstance(content, str):
        return content[:200]
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                return (b.get("text") or "")[:200]
    return ""


def cc_temporal() -> None:
    base = Path(os.path.expanduser("~")) / ".claude" / "projects"
    items: list[dict] = []
    for jsonl in base.rglob("*.jsonl"):
        first_ts = ""
        last_ts = ""
        cwd = ""
        git_branch = ""
        first_user_msg = ""
        try:
            with jsonl.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = d.get("timestamp")
                    if ts:
                        if not first_ts:
                            first_ts = ts
                        last_ts = ts
                    if not cwd and d.get("cwd"):
                        cwd = d["cwd"]
                    if not git_branch and d.get("gitBranch"):
                        git_branch = d["gitBranch"]
                    if d.get("type") == "user" and not first_user_msg:
                        msg = d.get("message") or {}
                        if isinstance(msg, dict):
                            first_user_msg = _extract_first_user_text(msg.get("content"))
        except OSError:
            continue
        items.append({
            "session_id": jsonl.stem,
            "project_dir": jsonl.parent.name,
            "first_ts": first_ts,
            "last_ts": last_ts,
            "cwd": cwd,
            "git_branch": git_branch,
            "first_user_msg": first_user_msg.replace("\n", " ").strip(),
        })
    items.sort(key=lambda x: x.get("first_ts") or "")
    out = {
        "generated_at": datetime.now().isoformat(),
        "source": str(base) + "/**/*.jsonl",
        "schema": "session_id -> (project_dir, first_ts, last_ts, cwd, git_branch, first_user_msg)",
        "date_range": [items[0]["first_ts"] if items else None,
                       items[-1]["first_ts"] if items else None],
        "count": len(items),
        "items": items,
    }
    p = write_out("cc_temporal.json", out)
    print(f"cc:      {len(items):>5} sessions -> {p.name}")


def fs_temporal() -> None:
    pe_path = REPO / "tools" / "fest-reconcile" / "portfolio_evidence.json"
    with pe_path.open(encoding="utf-8") as f:
        portfolio = json.load(f)
    items: list[dict] = []
    for it in portfolio.get("items", []):
        path_str = it.get("path", "")
        if not path_str:
            items.append({
                "name": it["name"],
                "surface": it["surface"],
                "path": None,
                "mtime": None,
                "ctime": None,
                "size_bytes": None,
                "error": "no_path_in_portfolio",
            })
            continue
        p = Path(path_str)
        if not p.is_absolute():
            p = REPO / path_str
        try:
            st = p.stat()
            items.append({
                "name": it["name"],
                "surface": it["surface"],
                "path": str(p),
                "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "ctime": datetime.fromtimestamp(st.st_ctime).isoformat(),
                "size_bytes": st.st_size if p.is_file() else None,
            })
        except OSError as e:
            items.append({
                "name": it["name"],
                "surface": it["surface"],
                "path": str(p),
                "mtime": None,
                "ctime": None,
                "size_bytes": None,
                "error": f"stat_failed: {type(e).__name__}",
            })
    items.sort(key=lambda x: x.get("ctime") or "")
    out = {
        "generated_at": datetime.now().isoformat(),
        "source": "portfolio_evidence.json + Path.stat()",
        "schema": "name -> (surface, path, mtime, ctime, size_bytes)",
        "count": len(items),
        "items": items,
    }
    out_path = write_out("fs_temporal.json", out)
    print(f"fs:      {len(items):>5} paths    -> {out_path.name}")


def write_progress(seqs_done: list[str]) -> None:
    progress_path = OUT_DIR / "_progress.json"
    if progress_path.exists():
        existing = json.loads(progress_path.read_text(encoding="utf-8"))
    else:
        existing = {"festival": "corpus-archaeology", "phases": {}}
    phase = existing["phases"].setdefault("001_TEMPORAL_INDEX", {})
    for seq in seqs_done:
        phase[seq] = {
            "status": "complete",
            "finished_at": datetime.now().isoformat(),
            "artifact": f"festival_out/{seq}_temporal.json",
        }
    progress_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("seq", choices=["chatgpt", "cc", "fs", "all"])
    args = p.parse_args()
    done: list[str] = []
    if args.seq in ("chatgpt", "all"):
        chatgpt_temporal()
        done.append("chatgpt")
    if args.seq in ("cc", "all"):
        cc_temporal()
        done.append("cc")
    if args.seq in ("fs", "all"):
        fs_temporal()
        done.append("fs")
    write_progress(done)
    print(f"\nProgress ledger updated: {OUT_DIR / '_progress.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
