"""
pull.py - corpus saver for real websites (Part B).

Two modes share the same output convention so the runner can score either:

  S-mode (single-file)
    `npx --yes single-file-cli <url> <out>/<name>.html`
    Produces a self-contained monolithic HTML with inlined CSS + base64 imgs.
    Use case: cascade-rule recall + occlusion math against frozen DOM.

  M-mode (multi-file)
    `node web-audit/bin/sitepull.mjs <url> --out <out>/<name> --no-smoke-test`
    Produces a directory tree with index.html + assets/css/.
    Use case: hydration + script-crash regression (the npmjs bug class).

Both modes write a sibling `<name>.expected.json` with smoke-only assertions
(min_labels=1, no should_find/filter checks). Runner uses `html_path` to
locate the actual HTML to load — `<name>.html` for S-mode, or
`<name>/app/public/index.html` for M-mode.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SITEPULL_BIN = Path("C:/Users/bruke/web-audit/bin/sitepull.mjs")




# ------------------------------ shared helpers ------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _atomic_write_text(path: Path, content: str) -> None:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False,
        dir=str(path.parent),
        prefix="." + path.name + ".", suffix=".tmp",
    )
    try:
        tmp.write(content)
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


def _safe_url(url: str) -> str:
    """Raise if url isn't http(s); return cleaned url."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"invalid url (need http/https): {url!r}")
    return url.strip()


def _load_url_list(urls: list[str], from_file: str | None) -> list[str]:
    pool: list[str] = []
    if from_file:
        for line in Path(from_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                pool.append(line)
    pool.extend(urls)
    return [_safe_url(u) for u in pool]


def _smoke_expected(
    file_id: str,
    source_url: str,
    html_path_rel: str,
    mode: str,
) -> dict:
    """Smoke-only expected.json — passes if the cascade produces >=1 label."""
    return {
        "file_id": file_id,
        "source_url": source_url,
        "kind": f"corpus-{mode}",
        "html_path": html_path_rel,
        "shapes_used": [],
        "min_labels": 1,
        "max_labels": 9999,
        "should_find": [],
        "should_filter": [],
    }


@dataclass(frozen=True)
class PullResult:
    file_id: str
    url: str
    mode: str
    html_path: str
    ok: bool
    error: str = ""
    duration_s: float = 0.0
    bytes: int = 0


# ------------------------------ S-mode (playwright snapshot) ------------------------------

# Originally planned to shell out to `npx single-file-cli`, but the subprocess
# plumbing on Windows hung between consecutive runs (chromium subprocess didn't
# exit cleanly, second pull blocked indefinitely). Switched to in-process
# playwright capture: same output shape (self-contained-ish r000.html),
# zero subprocess overhead, reuses the chromium playwright already manages.

_INLINE_STYLES_JS = r"""
async () => {
  // Best-effort inline external CSS so file:// loads don't depend on network.
  const links = [...document.querySelectorAll('link[rel~="stylesheet"]')];
  for (const link of links) {
    try {
      const r = await fetch(link.href, { credentials: 'omit' });
      if (!r.ok) continue;
      const css = await r.text();
      const style = document.createElement('style');
      style.setAttribute('data-from', link.href);
      style.textContent = css;
      link.replaceWith(style);
    } catch (e) { /* swallow — leave the link in place */ }
  }
  // Drop scripts so re-load doesn't re-execute hydration.
  for (const s of [...document.querySelectorAll('script,noscript')]) s.remove();
}
"""


def _pull_single_file(
    url: str,
    out_dir: Path,
    file_id: str,
    timeout_s: float,
    on_log,
    pw_browser,
) -> PullResult:
    import time
    out_html = out_dir / f"{file_id}.html"
    started = time.monotonic()

    page = pw_browser.new_page()
    try:
        page.goto(url, wait_until="networkidle",
                  timeout=int(timeout_s * 1000))
        page.evaluate(_INLINE_STYLES_JS)
        html = page.content()
    except Exception as e:
        try: page.close()
        except Exception: pass
        return PullResult(file_id, url, "S", out_html.name, False,
                          error=f"snapshot failed: {e!r}",
                          duration_s=time.monotonic() - started)
    finally:
        try: page.close()
        except Exception: pass

    out_html.write_text(html, encoding="utf-8")
    duration = time.monotonic() - started
    nbytes = out_html.stat().st_size
    on_log(f"  {file_id}  S  ok    {duration:5.1f}s  {nbytes/1024:7.1f} KB  {url}")
    return PullResult(file_id, url, "S", out_html.name, True,
                      duration_s=duration, bytes=nbytes)


# ------------------------------ M-mode (sitepull multi-file) ------------------------------

def _pull_multi_file(
    url: str,
    out_dir: Path,
    file_id: str,
    timeout_s: float,
    on_log,
) -> PullResult:
    import time
    if not SITEPULL_BIN.exists():
        return PullResult(file_id, url, "M", "", False,
                          error=f"sitepull not found at {SITEPULL_BIN}")

    target_dir = out_dir / file_id
    rel_html = f"{file_id}/app/public/index.html"
    cmd = [
        "node", str(SITEPULL_BIN),
        url,
        "--out", str(target_dir),
        "--no-smoke-test",
    ]
    started = time.monotonic()
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return PullResult(file_id, url, "M", rel_html, False,
                          error=f"timeout after {timeout_s:.0f}s",
                          duration_s=time.monotonic() - started)

    duration = time.monotonic() - started
    if cp.returncode != 0:
        snippet = (cp.stderr or cp.stdout or "")[:200].replace("\n", " ")
        return PullResult(file_id, url, "M", rel_html, False,
                          error=f"sitepull exit {cp.returncode}: {snippet}",
                          duration_s=duration)

    actual_html = out_dir / rel_html
    if not actual_html.exists():
        return PullResult(file_id, url, "M", rel_html, False,
                          error=f"sitepull ok but no index.html at {rel_html}",
                          duration_s=duration)

    nbytes = sum(p.stat().st_size for p in target_dir.rglob("*") if p.is_file())
    on_log(f"  {file_id}  M  ok    {duration:5.1f}s  {nbytes/1024:7.1f} KB  {url}")
    return PullResult(file_id, url, "M", rel_html, True,
                      duration_s=duration, bytes=nbytes)


# ------------------------------ orchestrator ------------------------------

def pull_corpus(
    urls: list[str],
    out_base: Path,
    mode: str,  # "S" or "M"
    run_id: str | None,
    timeout_s: float,
    start_index: int,
    on_log=print,
) -> tuple[Path, list[PullResult]]:
    """Pull `urls` into a corpus dir; return (run_dir, results)."""
    if mode not in ("S", "M"):
        raise ValueError(f"mode must be 'S' or 'M', got {mode!r}")

    effective_run_id = run_id or f"{_now_iso()}-pull{mode}"
    run_dir = out_base / effective_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    on_log(f"[fuzz pull] mode={mode}  out={run_dir}")
    on_log(f"[fuzz pull] {len(urls)} urls (timeout {timeout_s:.0f}s each)")

    results: list[PullResult] = []

    pw_ctx = None
    pw_browser = None
    if mode == "S":
        # Spin up a single chromium instance for all S-mode pulls.
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            on_log("[fuzz pull] playwright not installed. "
                   "pip install -r requirements-fuzz.txt && playwright install chromium")
            return run_dir, []
        pw_ctx = sync_playwright().start()
        pw_browser = pw_ctx.chromium.launch(headless=True)

    try:
        for i, url in enumerate(urls):
            file_id = f"r{start_index + i:03d}"
            if mode == "S":
                res = _pull_single_file(url, run_dir, file_id, timeout_s, on_log, pw_browser)
            else:
                res = _pull_multi_file(url, run_dir, file_id, timeout_s, on_log)
            results.append(res)

            if res.ok:
                expected = _smoke_expected(file_id, url, res.html_path, mode)
                _atomic_write_text(
                    run_dir / f"{file_id}.expected.json",
                    json.dumps(expected, indent=2, ensure_ascii=False) + "\n",
                )
            else:
                on_log(f"  {file_id}  {mode}  FAIL  {res.duration_s:5.1f}s  {res.error}")
    finally:
        if pw_browser:
            try: pw_browser.close()
            except Exception: pass
        if pw_ctx:
            try: pw_ctx.stop()
            except Exception: pass

    index = {
        "run_id": effective_run_id,
        "kind": f"corpus-{mode}",
        "created_at": _now_iso(),
        "generator_version": f"atl-fuzz-pull-{mode}@0.1.0",
        "count_attempted": len(urls),
        "count_ok": sum(1 for r in results if r.ok),
        "count_failed": sum(1 for r in results if not r.ok),
        "files": [
            {
                "file_id": r.file_id,
                "url": r.url,
                "ok": r.ok,
                "html_path": r.html_path,
                "duration_s": round(r.duration_s, 2),
                "bytes": r.bytes,
                "error": r.error,
            }
            for r in results
        ],
    }
    _atomic_write_text(
        run_dir / "index.json",
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
    )
    on_log(f"[fuzz pull] wrote {index['count_ok']}/{index['count_attempted']} "
           f"to {run_dir}")
    return run_dir, results
