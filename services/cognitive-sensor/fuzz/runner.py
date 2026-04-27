"""
runner.py — drive the anatomy extension across a fuzz corpus via Playwright.

Loads each f***.html, triggers auto-label, polls for the progress-panel
.done state, queries .anatomy-pinned-outline, scores against expected.json,
writes a report.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from fuzz.scorer import (
    FileResult,
    aggregate,
    make_error_result,
    score_file,
)

EXTENSION_PATH = (
    Path(__file__).resolve().parents[3]
    / "tools" / "anatomy-extension"
)

_LABEL_PROBE_JS = """
() => [...document.querySelectorAll('.anatomy-pinned-outline')]
    .filter(el => !el.closest('.anatomy-root'))
    .map(el => ({ id: el.id || '', tag: el.tagName.toLowerCase() }))
"""

_DONE_PROBE_JS = """
() => !!document.querySelector('.anatomy-progress.done')
"""

_TOGGLE_PROBE_JS = """
() => !!document.querySelector('.anatomy-toggle.anatomy-root')
"""

_HUD_ON_PROBE_JS = """
() => {
  const hud = document.querySelector('.anatomy-hud');
  return !!(hud && hud.classList.contains('on'));
}
"""


class PlaywrightMissing(RuntimeError):
    """Raised when the optional playwright dep isn't installed."""


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise PlaywrightMissing(
            "playwright not installed. To enable the runner:\n"
            "    pip install -r services/cognitive-sensor/requirements-fuzz.txt\n"
            "    playwright install chromium"
        ) from e
    return sync_playwright


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_extension_version(ext_path: Path) -> str:
    try:
        manifest = json.loads((ext_path / "manifest.json").read_text(encoding="utf-8"))
        return str(manifest.get("version", "?"))
    except Exception:
        return "?"


def _file_url(html_path: Path) -> str:
    """file:/// URL Playwright accepts on Windows + POSIX."""
    return html_path.resolve().as_uri()


def _atomic_write_json(path: Path, payload: Any) -> None:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False,
        dir=str(path.parent),
        prefix="." + path.name + ".", suffix=".tmp",
    )
    try:
        json.dump(payload, tmp, indent=2, ensure_ascii=False)
        tmp.write("\n")
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


def _iter_corpus_files(corpus_dir: Path, limit: int | None) -> Iterable[tuple[str, Path, dict]]:
    """Yield (file_id, html_path, expected_dict) in sorted order.

    Iterates all `*.expected.json` siblings; html_path comes from the
    `html_path` field in expected.json (fuzz files default to `<file_id>.html`).
    """
    expecteds = sorted(corpus_dir.glob("*.expected.json"))
    if limit is not None:
        expecteds = expecteds[:limit]
    for ep in expecteds:
        file_id = ep.name[: -len(".expected.json")]
        expected = json.loads(ep.read_text(encoding="utf-8"))
        rel = expected.get("html_path") or f"{file_id}.html"
        html = corpus_dir / rel
        if not html.exists():
            continue
        yield file_id, html, expected


def _poll_until(
    condition_fn,
    timeout_seconds: float,
    interval_seconds: float = 0.1,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if condition_fn():
            return True
        time.sleep(interval_seconds)
    return False


def _run_one_file(
    page,
    file_id: str,
    html_path: Path,
    expected: dict,
    timeout_seconds: float,
    on_log,
) -> FileResult:
    started = time.monotonic()

    try:
        page.goto(_file_url(html_path), timeout=int(timeout_seconds * 1000))
    except Exception as e:
        return make_error_result(
            file_id, f"page.goto failed: {e!r}",
            int((time.monotonic() - started) * 1000),
        )

    # Wait for the extension's toggle button to inject (always visible).
    toggle_ready = _poll_until(
        lambda: bool(page.evaluate(_TOGGLE_PROBE_JS)),
        timeout_seconds=min(10.0, timeout_seconds),
    )
    if not toggle_ready:
        return make_error_result(
            file_id, "extension toggle never injected (no .anatomy-toggle)",
            int((time.monotonic() - started) * 1000),
        )

    # Activate the extension — HUD stays hidden until state.on is true.
    try:
        page.click(".anatomy-toggle.anatomy-root", timeout=5_000)
    except Exception as e:
        return make_error_result(
            file_id, f"click toggle failed: {e!r}",
            int((time.monotonic() - started) * 1000),
        )

    hud_on = _poll_until(
        lambda: bool(page.evaluate(_HUD_ON_PROBE_JS)),
        timeout_seconds=min(5.0, timeout_seconds),
    )
    if not hud_on:
        return make_error_result(
            file_id, "HUD never activated after toggle click",
            int((time.monotonic() - started) * 1000),
        )

    # Trigger auto-label.
    try:
        page.click('.anatomy-root [data-act="auto"]', timeout=5_000)
    except Exception as e:
        return make_error_result(
            file_id, f"click auto-label failed: {e!r}",
            int((time.monotonic() - started) * 1000),
        )

    # Wait for the progress panel to mark .done. Auto-label scrolls; allow
    # most of the per-file budget here.
    done = _poll_until(
        lambda: bool(page.evaluate(_DONE_PROBE_JS)),
        timeout_seconds=timeout_seconds - (time.monotonic() - started),
    )
    if not done:
        # Take labels anyway — partial signal beats nothing.
        on_log(f"  {file_id}  WARN  .anatomy-progress.done never set; reading labels anyway")

    labeled = page.evaluate(_LABEL_PROBE_JS)
    duration_ms = int((time.monotonic() - started) * 1000)
    return score_file(expected, labeled, duration_ms)


def run(
    corpus_dir: Path,
    out_path: Path,
    limit: int | None,
    timeout_seconds: float,
    headless: bool,
    on_log=print,
) -> dict:
    """Run the fuzz corpus and return the report dict (also persisted to out_path)."""
    sync_playwright = _import_playwright()

    if not EXTENSION_PATH.exists():
        raise FileNotFoundError(f"extension not found at {EXTENSION_PATH}")

    if not corpus_dir.exists():
        raise FileNotFoundError(f"corpus dir not found: {corpus_dir}")

    index_path = corpus_dir / "index.json"
    corpus_index: dict = {}
    if index_path.exists():
        corpus_index = json.loads(index_path.read_text(encoding="utf-8"))

    on_log(f"[fuzz run] corpus:    {corpus_dir}")
    on_log(f"[fuzz run] extension: {EXTENSION_PATH} (v{_read_extension_version(EXTENSION_PATH)})")

    user_data_dir = Path(tempfile.mkdtemp(prefix="atl-fuzz-udd-"))
    results: list[FileResult] = []
    chromium_version = "?"

    try:
        with sync_playwright() as p:
            ext_str = str(EXTENSION_PATH)
            args = [
                f"--disable-extensions-except={ext_str}",
                f"--load-extension={ext_str}",
            ]
            if headless:
                args.append("--headless=new")

            context = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=False,  # Always pass False; --headless=new in args overrides.
                args=args,
                viewport={"width": 1280, "height": 800},
            )
            try:
                chromium_version = context.browser.version if context.browser else "?"
                on_log(f"[fuzz run] chromium:  {chromium_version}")

                files = list(_iter_corpus_files(corpus_dir, limit))
                on_log(f"[fuzz run] running {len(files)} files "
                       f"({'headless' if headless else 'headed'}, "
                       f"timeout {timeout_seconds:.0f}s each)")

                for file_id, html_path, expected in files:
                    page = context.new_page()
                    try:
                        result = _run_one_file(
                            page, file_id, html_path, expected,
                            timeout_seconds, on_log,
                        )
                    except Exception as e:
                        result = make_error_result(file_id, f"unhandled: {e!r}", 0)
                    finally:
                        try:
                            page.close()
                        except Exception:
                            pass
                    results.append(result)

                    line = (
                        f"  {file_id}  {result['status']:<5}  "
                        f"{result['duration_ms']/1000:.1f}s  "
                        f"{result['actual_label_count']} labels "
                        f"({result['expected_min']}..{result['expected_max']})"
                    )
                    if result["status"] != "pass":
                        extra = []
                        if result["filter_violations"]:
                            extra.append(f"violations={len(result['filter_violations'])}")
                        if result["errors"]:
                            extra.append(f"err={result['errors'][0][:60]}")
                        if extra:
                            line += "  · " + ", ".join(extra)
                    on_log(line)
            finally:
                try:
                    context.close()
                except Exception:
                    pass
    finally:
        shutil.rmtree(user_data_dir, ignore_errors=True)

    report = {
        "runner_version": "atl-fuzz-runner@0.1.0",
        "started_at": _now_iso(),
        "ended_at": _now_iso(),
        "corpus": {
            "run_id": corpus_index.get("run_id", corpus_dir.name),
            "path": str(corpus_dir),
            "seed": corpus_index.get("seed"),
            "count": corpus_index.get("count"),
        },
        "chromium_version": chromium_version,
        "extension_version": _read_extension_version(EXTENSION_PATH),
        "totals": aggregate(results),
        "results": results,
    }
    _atomic_write_json(out_path, report)
    on_log(f"[fuzz run] wrote report: {out_path}")
    t = report["totals"]
    on_log(f"[fuzz run] totals: {t['files']} files · "
           f"{t['pass']} pass · {t['fail']} fail · {t['error']} error")
    return report


def latest_corpus_dir(base: Path) -> Path | None:
    """Return the most-recently-modified subdir under `base`, or None."""
    if not base.exists():
        return None
    subdirs = [p for p in base.iterdir() if p.is_dir()]
    if not subdirs:
        return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)
