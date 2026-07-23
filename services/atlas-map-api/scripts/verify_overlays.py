"""Verify every atlas.surface.json: it loads, and each declared endpoint is real.

Evidence rule (code-as-furniture): a self-description must not declare furniture
that isn't there. For each capability's `invoke` ("METHOD /path"), we confirm the
most-specific literal path segment appears somewhere in that service's source —
a hallucinated route would not. Exit non-zero if any overlay is malformed or any
endpoint can't be located.

Not every surface's source lives under its own services/apps/tools directory —
some (e.g. delta-scp-demo) are overlays for a service that actually lives in a
sibling repo on disk. For those, the co-location scan finds nothing by design,
so we fall back to reading the exact file the capability's own `evidence` field
cites and checking the token there — the overlay is trusted to cite real code,
not to be reachable by directory-tree proximity.

Run: ./.venv/Scripts/python.exe scripts/verify_overlays.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from atlas_map_api import describe as d
from atlas_map_api.loader import load_snapshot

_PRUNE = {"node_modules", ".venv", ".git", "dist", "__pycache__", ".pytest_cache", "build"}
_SRC_EXT = {".py", ".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs"}
_EVIDENCE_PATH_RE = re.compile(r"^\s*((?:[A-Za-z]:)?[^:]+):\d")


def _service_sources(service_dir: Path) -> list[str]:
    texts: list[str] = []
    for p in service_dir.rglob("*"):
        if p.is_dir():
            continue
        if any(part in _PRUNE for part in p.parts):
            continue
        if p.suffix in _SRC_EXT:
            try:
                texts.append(p.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return texts


def _path_token(invoke: str) -> str | None:
    """Most-specific literal path segment of an 'METHOD /a/b/:id' invoke string."""
    parts = invoke.split()
    path = next((p for p in parts if p.startswith("/")), parts[-1] if parts else "")
    segs = [s for s in path.split("/") if s and ":" not in s and "{" not in s]
    return max(segs, key=len) if segs else None


def _evidence_file(evidence: str, repo_root: Path) -> Path | None:
    """Resolve the file an `evidence` citation points at, if any.

    Handles "path:line", "path:line-line", and "path:line (...)" shapes, plus
    Windows absolute paths (the "C:" drive prefix isn't a field separator).
    Relative citations resolve against repo_root; only the first cited file in
    a multi-file citation ("a.js:1; b.js:2") is used — good enough to confirm
    the surface points at real code, which is all this check needs.
    """
    m = _EVIDENCE_PATH_RE.match(evidence)
    if not m:
        return None
    raw = m.group(1).strip()
    p = Path(raw)
    return p if p.is_absolute() else repo_root / raw


def _token_verified_by_evidence(tok: str, evidence: str, repo_root: Path) -> bool:
    p = _evidence_file(evidence, repo_root)
    if p is None or not p.is_file():
        return False
    try:
        return tok in p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def main() -> int:
    repo_root = load_snapshot().repo_root
    surfaces = d.described_surfaces(repo_root)
    print(f"Verifying {len(surfaces)} described surfaces under {repo_root}\n")

    failures: list[str] = []
    total_caps = 0
    for name in surfaces:
        overlay = d.load_overlay(repo_root, name)
        if overlay is None:
            failures.append(f"{name}: overlay failed to load / malformed")
            print(f"  [FAIL] {name}: malformed overlay")
            continue
        if not overlay.capabilities:
            # Zero capabilities is CORRECT for retired/stub surfaces — they self-
            # describe as "don't build on this" and deliberately expose nothing.
            if overlay.lifecycle in ("retired", "stub"):
                print(f"  [ ok ] {name}: tagged {overlay.lifecycle}, no capabilities (by design)")
            else:
                failures.append(f"{name}: live surface with zero capabilities")
                print(f"  [FAIL] {name}: live but zero capabilities")
            continue

        total_caps += len(overlay.capabilities)
        # Endpoint-existence check only applies to HTTP surfaces. CLI/UI/websocket
        # surfaces declare commands/affordances, not routes — load-check only.
        if overlay.kind != "http":
            tag = f"{overlay.kind}/{overlay.lifecycle}"
            print(f"  [ ok ] {name}: {len(overlay.capabilities)} capabilities ({tag}, not endpoint-checked)")
            continue

        svc_dir = next((repo_root / g / name for g in ("services", "apps", "tools")
                        if (repo_root / g / name).is_dir()), repo_root / "services" / name)
        sources = _service_sources(svc_dir)
        missing: list[str] = []
        for cap in overlay.capabilities:
            tok = _path_token(cap.invoke)
            if tok is None:
                continue  # no literal segment to check (e.g. "/")
            if any(tok in src for src in sources):
                continue
            if cap.evidence and _token_verified_by_evidence(tok, cap.evidence, repo_root):
                continue
            missing.append(f"{cap.id} ({cap.invoke} -> '{tok}')")
        if missing:
            failures.append(f"{name}: {len(missing)} endpoint(s) not found in source: {missing}")
            print(f"  [FAIL] {name}: {len(missing)} unverifiable: {missing}")
        else:
            print(f"  [ ok ] {name}: {len(overlay.capabilities)} capabilities, all endpoints located")

    print(f"\n{len(surfaces)} surfaces, {total_caps} capabilities checked.")
    if failures:
        print(f"FAILED: {len(failures)} problem(s).")
        return 1
    print("ALL OVERLAYS VERIFIED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
