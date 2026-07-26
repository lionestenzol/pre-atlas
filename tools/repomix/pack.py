#!/usr/bin/env python3
"""repomix seam adapter -- the CARRY stage: a scoped, content-addressed full-content
bundle of a repo region, emitted as a stdout JSON receipt.

The perceive stage (delta-scp / repo-inventory / code-recon) is LOSSY on purpose --
skeletons and censuses, cheap. CARRY is the lossless lane: repomix packs the actual
file contents of a scope into one document an LLM can read whole. This wrapper makes
that lane seam-ready -- it runs repomix, parks the bundle in a content-addressed cache,
and prints a receipt whose `sha256` is the bundle's content-address (the seam join key).
The heavy bytes stay in the cache file; the receipt is a small pointer + metrics, so a
Receipt / the ledger never inlines a multi-MB pack (same shape as tools/binre/report.py,
which addresses out/<sha>/ rather than inlining it).

assemble-first: a thin wrapper over the `repomix` CLI (npm, 1.15.x). repomix already
does the packing, the ignore rules, the tokenizing; we add only the content-address +
receipt. No reimplementation -- a generic packer would be WORSE, not just later
(see ~/.claude/rules/common/assemble-first.md).

Content-address: repomix output is deterministic for a fixed scope (verified: two runs
-> identical sha; no wall-clock in the header; relative paths only), so the sha256 over
the bundle bytes is a stable, machine-independent join key.

Gateway note: through the seam gateway only `{root}` (a forward-slash path scope) is
passed -- the arg charset rejects `*`, so glob `--include` is a STANDALONE-only feature.
Scope by directory for the gateway path. repomix has node startup cost (~5s for a tiny
dir) so a large scope can approach the 20s gateway timeout -- scope it (see notes).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Repo root = three up from tools/repomix/pack.py, so the carry cache is stable
# regardless of the caller's cwd (the gateway runs us with cwd=repo_root anyway).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CACHE = Path(os.environ.get("SEAM_CARRY_DIR", str(_REPO_ROOT / ".seam" / "carry")))

_EXT = {"xml": "xml", "markdown": "md", "json": "json", "plain": "txt"}


def _receipt(**kw) -> int:
    """Print a one-line JSON receipt and return an exit code (0 ok/absence, nonzero fail)."""
    kw.setdefault("tool", "repomix")
    kw.setdefault("op", "pack")
    print(json.dumps(kw))
    return int(kw.pop("_exit", 0))


def _file_count(text: str, style: str) -> int | None:
    if style == "xml":
        return text.count('<file path="')
    if style == "markdown":
        return text.count("\n## File: ") + (1 if text.startswith("## File: ") else 0)
    return None  # json/plain: not cheaply countable without parsing; leave unknown


def pack(scope: str, *, style: str = "xml", include: str | None = None,
         ignore: str | None = None, compress: bool = False,
         out: str | None = None) -> dict:
    """Run repomix over `scope`, content-address the bundle, return a receipt dict."""
    if not Path(scope).exists():
        return {"found": False, "error": f"scope does not exist: {scope!r}", "_exit": 2}

    exe = shutil.which("repomix")
    if exe is None:
        return {"found": False, "error": "repomix not on PATH (npm i -g repomix)", "_exit": 1}

    style = style if style in _EXT else "xml"
    tmp = Path(tempfile.mkdtemp(prefix="seam-carry-")) / f"pack.{_EXT[style]}"
    cmd = [exe, scope, "-o", str(tmp), "--style", style, "--quiet"]
    if include:
        cmd += ["--include", include]
    if ignore:
        cmd += ["--ignore", ignore]
    if compress:
        cmd += ["--compress"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=19, cwd=str(Path.cwd()))
    except subprocess.TimeoutExpired:
        return {"found": False, "error": "repomix timed out (scope too large -- narrow it)", "_exit": 1}
    if proc.returncode != 0 or not tmp.exists():
        err = (proc.stderr or proc.stdout or "repomix failed").strip().splitlines()
        return {"found": False, "error": (err[-1] if err else "repomix failed")[:200], "_exit": 1}

    data = tmp.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8", errors="replace")

    # Park the bundle in the content-addressed cache (idempotent: same content -> same path).
    dest_dir = Path(out) if out else _CACHE
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{digest}.{_EXT[style]}"
    if not dest.exists():
        dest.write_bytes(data)
    try:
        tmp.unlink()
        tmp.parent.rmdir()
    except OSError:
        pass

    return {
        "found": True,
        "sha256": digest,
        "scope": scope,
        "style": style,
        "compressed": compress,
        "char_count": len(text),
        "file_count": _file_count(text, style),
        "approx_tokens": len(text) // 4,
        "path": str(dest).replace("\\", "/"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="pack.py", description="repomix CARRY seam adapter -> content-addressed bundle receipt")
    ap.add_argument("root", help="scope: a repo / directory path (forward slashes)")
    ap.add_argument("--style", default="xml", choices=sorted(_EXT), help="bundle format (default xml)")
    ap.add_argument("--include", help="glob(s) to include -- STANDALONE only (gateway rejects '*')")
    ap.add_argument("--ignore", help="extra glob(s) to exclude")
    ap.add_argument("--compress", action="store_true", help="essential-structure compression (smaller)")
    ap.add_argument("--out", help="override the carry cache dir for this run")
    a = ap.parse_args(argv)
    return _receipt(**pack(a.root, style=a.style, include=a.include,
                           ignore=a.ignore, compress=a.compress, out=a.out))


if __name__ == "__main__":
    raise SystemExit(main())
