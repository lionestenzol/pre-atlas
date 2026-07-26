"""DropList control CLI — talks to a running DropList server, LLM-friendly.

A separate surface from droplist.cli (the intake/read helper). This one is the
operator/agent front door: state, list, drop, flip, ask, serve — every command
supports ``--json`` so an LLM subprocess call gets the same shape a human reads.

Discovery order for the target server URL:
  1. ``--url`` flag on the command line
  2. ``DROPLIST_URL`` env var (full base URL, e.g. ``http://127.0.0.1:58014``)
  3. ``data/port.txt`` in the resolved data dir (written by ``server.py`` on boot)
  4. ``DROPLIST_PORT`` env var, else ``3073``

Write commands look for a token in the same order:
  1. ``--token`` flag
  2. ``ATLAS_WRITE_TOKEN`` env var
  3. ``data/write_token.txt`` (written by ``server.py`` on boot)

Stdlib-only (urllib + argparse) so it runs from the frozen exe, a source
checkout, or a scratch venv without extra installs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


def _default_data_dir() -> Path:
    if os.environ.get("DROPLIST_DATA"):
        return Path(os.environ["DROPLIST_DATA"])
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "DropList" / "data"


def _discover_url(explicit: Optional[str]) -> str:
    if explicit:
        return explicit.rstrip("/")
    env = os.environ.get("DROPLIST_URL")
    if env:
        return env.rstrip("/")
    port_file = _default_data_dir() / "port.txt"
    port: Optional[int] = None
    try:
        if port_file.is_file():
            port = int(port_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        port = None
    if port is None:
        port = int(os.environ.get("DROPLIST_PORT", "3073"))
    return f"http://127.0.0.1:{port}"


def _discover_token(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit
    env = os.environ.get("ATLAS_WRITE_TOKEN")
    if env:
        return env.strip()
    tf = _default_data_dir() / "write_token.txt"
    try:
        if tf.is_file():
            return tf.read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    return None


class ServerError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:400]}")
        self.status = status
        self.body = body


def _request(method: str, url: str, *, body: Any = None,
             token: Optional[str] = None, timeout: float = 15.0) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["X-Atlas-Token"] = token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — local http only
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise ServerError(e.code, e.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        raise ServerError(0, f"server unreachable: {e.reason}")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _print_json(obj: Any) -> None:
    json.dump(obj, sys.stdout, indent=2, sort_keys=False, default=str)
    sys.stdout.write("\n")


def _print_summary_human(s: dict) -> None:
    c = s.get("counts") or {}
    ex = c.get("by_executor") or {}
    st = c.get("by_status") or {}
    print(f"time            {s.get('time','')}")
    print(f"dags            {c.get('total',0)} total  ·  {c.get('open',0)} open  ·  {c.get('complete',0)} complete")
    print(f"by executor     human={ex.get('human',0)}  ai={ex.get('ai',0)}")
    if st:
        pairs = "  ".join(f"{k}={v}" for k, v in sorted(st.items()))
        print(f"by status       {pairs}")
    ai = s.get("ai") or {}
    models = ai.get("available_models") or []
    if models:
        print(f"models          {', '.join(m['id'] for m in models)}")
        print(f"default model   {ai.get('default_model') or '(none)'}")
    kc = ai.get("keys_configured") or {}
    set_keys = [k for k, v in kc.items() if v]
    if set_keys:
        print(f"keys set for    {', '.join(set_keys)}")
    top = s.get("top_dags") or []
    if top:
        print("")
        print(f"top {len(top)} open DAG(s):")
        for d in top:
            tag = "AI " if d.get("executor") == "ai" else "HUM"
            print(f"  [{tag}] {d['dag_id']:<20} {d.get('status',''):<10}  {(d.get('goal') or '')[:70]}")
            if d.get("next_move"):
                print(f"       next: {d['next_move'][:80]}")


def _print_dag_list_human(dags: list[dict]) -> None:
    if not dags:
        print("(none)")
        return
    for d in dags:
        tag = "AI " if d.get("executor") == "ai" else "HUM"
        print(f"[{tag}] {d['dag_id']:<20} {d.get('status',''):<10}  {(d.get('goal') or '')[:80]}")


def cmd_summary(args: argparse.Namespace) -> int:
    url = _discover_url(args.url)
    q = f"?open_only={'1' if args.open_only else '0'}&top={args.top}"
    data = _request("GET", f"{url}/api/summary{q}")
    (_print_json if args.json else _print_summary_human)(data)
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    url = _discover_url(args.url)
    summary = _request("GET", f"{url}/api/summary?top={args.top}")
    state = _request("GET", f"{url}/api/state")
    payload = {"summary": summary, "state": state}
    if args.json:
        _print_json(payload)
        return 0
    _print_summary_human(summary)
    print("")
    due = state.get("due_today") or []
    if due:
        print(f"recurring due   {len(due)} item(s)")
    lr = state.get("locked_refs") or {}
    if lr:
        print(f"locked refs     {len(lr)}")
    return 0


def cmd_ls(args: argparse.Namespace) -> int:
    url = _discover_url(args.url)
    qs = []
    if args.tab:
        qs.append(f"executor={args.tab}")
    if args.status:
        qs.append(f"status={args.status}")
    if args.limit:
        qs.append(f"limit={args.limit}")
    q = ("?" + "&".join(qs)) if qs else ""
    data = _request("GET", f"{url}/api/dags{q}")
    dags = data.get("dags") or []
    (_print_json if args.json else _print_dag_list_human)({"dags": dags} if args.json else dags)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    url = _discover_url(args.url)
    data = _request("GET", f"{url}/api/dag/{args.dag_id}")
    if args.json:
        _print_json(data)
        return 0
    print(f"{data.get('dag_id','?')}  ({data.get('status','')})")
    print(f"  goal:     {data.get('goal','')}")
    print(f"  domain:   {data.get('domain','')}")
    print(f"  executor: {data.get('executor','human')}")
    for n in data.get("nodes") or []:
        mark = "x" if n.get("status") == "done" else (">" if n.get("status") == "ready" else "-")
        print(f"  [{mark}] {n.get('id',''):<10} {n.get('title','')}")
    return 0


def cmd_drop(args: argparse.Namespace) -> int:
    url = _discover_url(args.url)
    token = _discover_token(args.token)
    if not token:
        print("no write token found — start the server once, or set ATLAS_WRITE_TOKEN", file=sys.stderr)
        return 2
    text = args.text or (sys.stdin.read() if not sys.stdin.isatty() else "")
    text = text.strip()
    if not text:
        print("nothing to drop — pass text or pipe on stdin", file=sys.stderr)
        return 2
    data = _request("POST", f"{url}/api/drop", body={"raw": text}, token=token)
    if args.json:
        _print_json(data)
    else:
        print(f"dropped: {data.get('drop_id') or data.get('id') or 'ok'}")
    return 0


def cmd_flip(args: argparse.Namespace) -> int:
    url = _discover_url(args.url)
    token = _discover_token(args.token)
    if not token:
        print("no write token found — start the server once, or set ATLAS_WRITE_TOKEN", file=sys.stderr)
        return 2
    data = _request("POST", f"{url}/api/dag/{args.dag_id}/executor",
                    body={"executor": args.to}, token=token)
    if args.json:
        _print_json(data)
    else:
        print(f"{args.dag_id} -> {data.get('executor','?')}")
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    url = _discover_url(args.url)
    data = _request("GET", f"{url}/api/ai/models")
    if args.json:
        _print_json(data)
        return 0
    default = data.get("default")
    for m in data.get("models") or []:
        marker = "*" if m["id"] == default else " "
        print(f" {marker} {m['id']}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    url = _discover_url(args.url)
    token = _discover_token(args.token)
    if not token:
        print("no write token found — start the server once, or set ATLAS_WRITE_TOKEN", file=sys.stderr)
        return 2
    models = _request("GET", f"{url}/api/ai/models")
    model = args.model or models.get("default")
    if not model:
        print("no model available — configure one first (see `droplist models`)", file=sys.stderr)
        return 2
    text = args.text or (sys.stdin.read() if not sys.stdin.isatty() else "")
    text = text.strip()
    if not text:
        print("nothing to ask — pass text or pipe on stdin", file=sys.stderr)
        return 2
    body = {"model": model, "messages": [{"role": "user", "content": text}], "max_tokens": args.max_tokens}
    data = _request("POST", f"{url}/api/ai/complete", body=body, token=token, timeout=180.0)
    if args.json:
        _print_json(data)
        return 0
    for block in data.get("content") or []:
        if block.get("type") == "text":
            print(block.get("text", ""))
    return 0


def cmd_port(args: argparse.Namespace) -> int:
    print(_discover_url(args.url))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Run the DropList server in the foreground (no desktop window). Useful
    when you want a headless server for the CLI + LLMs to talk to."""
    # Import here so `droplist ls` etc. don't pay uvicorn / fastapi import cost.
    from . import server
    port = args.port if args.port is not None else int(os.environ.get("DROPLIST_PORT", "3073"))
    print(f"[droplist] serving on http://{args.host}:{port}  (Ctrl-C to stop)")
    server.run(port=port, host=args.host)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="droplist",
        description="DropList control CLI — read + write against a running DropList server.",
    )
    p.add_argument("--url", help="Base URL of the DropList server (default: auto-discover)")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of the human summary")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("summary", help="One-call state snapshot — the LLM's front door")
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--all", dest="open_only", action="store_false",
                   help="Include complete DAGs (default: open only)")
    s.set_defaults(open_only=True, func=cmd_summary)

    s = sub.add_parser("state", help="Summary + recurring + due_today + locked refs")
    s.add_argument("--top", type=int, default=10)
    s.set_defaults(func=cmd_state)

    s = sub.add_parser("ls", help="List DAG summaries")
    s.add_argument("--tab", choices=["human", "ai"], help="Filter by executor tab")
    s.add_argument("--status", help="Filter by status (running, complete, ...)")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_ls)

    s = sub.add_parser("show", help="Show one DAG with its nodes")
    s.add_argument("dag_id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("drop", help="Capture a new drop (arg or stdin)")
    s.add_argument("text", nargs="?")
    s.add_argument("--token")
    s.set_defaults(func=cmd_drop)

    s = sub.add_parser("flip", help="Move a DAG between Human and AI tabs")
    s.add_argument("dag_id")
    s.add_argument("to", choices=["human", "ai"])
    s.add_argument("--token")
    s.set_defaults(func=cmd_flip)

    s = sub.add_parser("models", help="List available AI models")
    s.set_defaults(func=cmd_models)

    s = sub.add_parser("ask", help="Send a prompt to the default AI model and print the reply")
    s.add_argument("text", nargs="?")
    s.add_argument("--model")
    s.add_argument("--max-tokens", type=int, default=1024)
    s.add_argument("--token")
    s.set_defaults(func=cmd_ask)

    s = sub.add_parser("port", help="Print the discovered server base URL")
    s.set_defaults(func=cmd_port)

    s = sub.add_parser("serve", help="Run the server in the foreground (no desktop window)")
    s.add_argument("--port", type=int, default=None)
    s.add_argument("--host", default="127.0.0.1")
    s.set_defaults(func=cmd_serve)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except ServerError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
