#!/usr/bin/env python3
"""deepwiki-open seam adapter -- the NARRATE stage: read a repo's generated wiki
(the narrator's artifact) as a content-addressed stdout JSON receipt.

perceive = structure (lossy), carry = full content (lossless), NARRATE = prose: the
human-readable explanation of what a repo IS and how it hangs together. deepwiki-open
generates that wiki (local/private, Ollama-backed). This wrapper exposes the FAST,
deterministic, seam-safe slice of it -- reading the *cached* wiki via the backend's
GET /api/wiki_cache (api/api.py:463) -- and content-addresses it as the join key.

Why only the cached read through the seam: generating a wiki or answering a live RAG
question runs Ollama for tens of seconds to minutes -- it cannot fit the 20s gateway
timeout, and a stochastic LLM answer has no stable content-address anyway. So NARRATE
mirrors code-recon's orient: expose the READ of the cached artifact (fast, hashable),
not the regeneration. The live Q&A lane is here too (`--ask`) but is STANDALONE-only --
it is never reached through the gateway, by design (same posture as gw index regen).

assemble-first: deepwiki-open does all the wiki generation + RAG; we add only the
content-address + receipt over its existing HTTP cache read. stdlib only (urllib), so
the wrapper has no deps of its own.

Trust: a wiki is a NARRATOR artifact -- it confabulates. Per the lattice doctrine
([[feedback_agent_report_distrust]]) a NARRATE receipt is a hypothesis to be proven by
a PROVER (code-recon) before any decision rests on it; the seam join key is what lets
you pin "the wiki said X about THIS exact content" to a code-recon verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_BASE = os.environ.get("DEEPWIKI_URL", "http://localhost:8001").rstrip("/")
_VOLATILE = {"generated_at", "created_at", "updated_at", "timestamp", "date", "cached_at"}


def _receipt(**kw) -> int:
    kw.setdefault("tool", "deepwiki")
    kw.setdefault("op", "wiki")
    print(json.dumps(kw))
    return int(kw.pop("_exit", 0))


def _scrub(obj):
    """Drop volatile keys recursively so the content-address is stable across regens."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if k not in _VOLATILE}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def _derive(repo: str) -> tuple[str, str, str]:
    """(owner, repo, repo_type) from a github/gitlab URL or a local path."""
    r = repo.rstrip("/")
    for host, rtype in (("github.com", "github"), ("gitlab.com", "gitlab"), ("bitbucket.org", "bitbucket")):
        if host in r:
            parts = r.split(host, 1)[1].strip("/").split("/")
            if len(parts) >= 2:
                return parts[0], parts[1].removesuffix(".git"), rtype
    p = Path(r)
    owner = p.parent.name or "local"
    return owner, p.name or "repo", "local"


def read_wiki(repo: str, *, owner: str | None = None, name: str | None = None,
              repo_type: str | None = None, language: str = "en", timeout: float = 8.0) -> dict:
    """GET /api/wiki_cache, content-address the result. found:false on absence/down."""
    o, n, t = _derive(repo)
    owner, name, repo_type = owner or o, name or n, repo_type or t
    qs = urllib.parse.urlencode({"owner": owner, "repo": name, "repo_type": repo_type, "language": language})
    url = f"{_BASE}/api/wiki_cache?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace").strip()
    except urllib.error.URLError as e:
        return {"found": False, "repo": repo, "reason": f"deepwiki backend unreachable at {_BASE} ({e.reason})"}
    except Exception as e:  # noqa: BLE001 -- any transport error is a clean absence, not a crash
        return {"found": False, "repo": repo, "reason": f"deepwiki read failed: {e}"}

    if not body or body == "null":
        return {"found": False, "repo": repo, "owner": owner, "repo_type": repo_type,
                "reason": "no cached wiki for this repo (generate one first)"}
    try:
        cached = json.loads(body)
    except json.JSONDecodeError:
        return {"found": False, "repo": repo, "reason": "wiki cache returned non-JSON"}

    canon = _scrub(cached)
    digest = hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    structure = cached.get("wiki_structure") or cached.get("structure") or {}
    pages = structure.get("pages") if isinstance(structure, dict) else None
    gen = cached.get("generated_pages") or {}
    return {
        "found": True,
        "sha256": digest,
        "repo": repo,
        "owner": owner,
        "repo_type": repo_type,
        "language": language,
        "title": structure.get("title") if isinstance(structure, dict) else None,
        "page_count": len(pages) if isinstance(pages, (list, dict)) else (len(gen) if gen else None),
    }


def ask_live(repo: str, question: str, *, timeout: float = 180.0) -> dict:
    """STANDALONE-only live RAG via POST /chat/completions/stream. Slow; not seam-exposed."""
    o, n, t = _derive(repo)
    payload = {
        "repo_url": repo, "type": t,
        "messages": [{"role": "user", "content": question}],
    }
    req = urllib.request.Request(
        f"{_BASE}/chat/completions/stream",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            answer = resp.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return {"tool": "deepwiki", "op": "ask", "found": False, "repo": repo, "reason": str(e), "_exit": 1}
    return {"tool": "deepwiki", "op": "ask", "found": True, "repo": repo,
            "question": question, "answer": answer.strip()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ask.py", description="deepwiki-open NARRATE seam adapter (cached-wiki read; --ask = live lane)")
    ap.add_argument("repo", help="repo URL (github/gitlab) or local path")
    ap.add_argument("--owner", help="override derived owner")
    ap.add_argument("--name", help="override derived repo name")
    ap.add_argument("--repo-type", help="override derived type (github|gitlab|local)")
    ap.add_argument("--language", default="en", help="wiki language (default en)")
    ap.add_argument("--ask", metavar="Q", help="STANDALONE live RAG question (slow; not via gateway)")
    a = ap.parse_args(argv)
    if a.ask:
        return _receipt(**ask_live(a.repo, a.ask))
    return _receipt(**read_wiki(a.repo, owner=a.owner, name=a.name,
                                repo_type=a.repo_type, language=a.language))


if __name__ == "__main__":
    raise SystemExit(main())
