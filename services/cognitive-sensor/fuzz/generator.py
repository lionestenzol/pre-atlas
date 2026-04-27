"""
generator.py — drive the fuzz corpus generation.

Deterministic given (seed, count). Writes one directory with paired HTML +
expected.json per file, plus an index.json catalog and a short README.

Consumers (the future Playwright runner) read:
  • `index.json` — run metadata + shape catalog
  • `f***.html` — load into the browser, trigger auto-label
  • `f***.expected.json` — score the resulting labels
"""
from __future__ import annotations

import json
import os
import random
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fuzz import envelope
from fuzz.shapes import (
    FILTER_SHAPE_NAMES,
    FIRING_SHAPE_NAMES,
    SHAPE_REGISTRY,
    Fragment,
)


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` via tempfile + fsync + replace."""
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _pick_shapes_for_file(rng: random.Random) -> list[str]:
    """Pick a deterministic list of shape names for one file."""
    firing_pool = sorted(FIRING_SHAPE_NAMES)
    filter_pool = sorted(FILTER_SHAPE_NAMES)

    num_shapes = rng.randint(3, 8)
    # Bias ~70/30 firing/filter, capped by pool sizes.
    num_filter = min(rng.randint(0, 2), num_shapes, len(filter_pool))
    num_firing = min(num_shapes - num_filter, len(firing_pool))

    picked_firing = rng.sample(firing_pool, num_firing)
    picked_filter = rng.sample(filter_pool, num_filter)
    picks = picked_firing + picked_filter
    rng.shuffle(picks)
    return picks


def _build_fragments(
    rng: random.Random, file_idx: int, shape_names: list[str]
) -> list[Fragment]:
    fragments: list[Fragment] = []
    for j, name in enumerate(shape_names):
        anchor_id = f"fz-{file_idx:03d}-{j:02d}-{name}"
        fragments.append(SHAPE_REGISTRY[name](rng, anchor_id))
    return fragments


def _build_expected(
    file_id: str, seed: int, fragments: list[Fragment]
) -> dict:
    firing = [f for f in fragments if f.should_fire]
    non_firing = [f for f in fragments if not f.should_fire]
    expected_label_count = sum(f.labels_produced for f in firing)
    # min_labels is conservative — the cascade misses some shapes (pattern-repeat,
    # occlusion, dedupe) and real recall is ~50%. Setting min to half the expected
    # count leaves room for legitimate misses while still flagging catastrophic
    # under-firing (0-1 labels when 8 shapes were present).
    min_labels = max(1, expected_label_count // 2) if firing else 0
    max_labels = expected_label_count + sum(f.slop for f in fragments) + 2
    return {
        "file_id": file_id,
        "seed": seed,
        "kind": "fuzz",
        "html_path": f"{file_id}.html",
        "shapes_used": [f.intent for f in fragments],
        "min_labels": min_labels,
        "max_labels": max_labels,
        "should_find": [
            {"intent": f.intent, "anchor_id": f.anchor_id,
             "labels_produced": f.labels_produced}
            for f in firing
        ],
        "should_filter": [
            {"intent": f.intent, "anchor_id": f.anchor_id}
            for f in non_firing
        ],
    }


def _catalog() -> list[dict]:
    """Probe shapes once (rng seeded 0) to dump their intent table."""
    probe_rng = random.Random(0)
    rows = []
    for name, fn in SHAPE_REGISTRY.items():
        frag = fn(probe_rng, "__catalog__")
        rows.append({
            "name": name,
            "should_fire": frag.should_fire,
            "labels_produced": frag.labels_produced,
            "slop": frag.slop,
        })
    return rows


_README = """# atl fuzz corpus · {run_id}

Deterministic HTML fixtures for stress-testing the anatomy extension
auto-label cascade. Seed: `{seed}`. Files: `{count}`.

## Layout
- `index.json` — run metadata + shape catalog
- `f***.html` — open in Chrome with the anatomy extension loaded
- `f***.expected.json` — sibling assertion file (read by the test runner)

## Quick check (manual)
1. `cd services/cognitive-sensor` · confirm extension is loaded in Chrome.
2. Open `file:///{abs_dir}/f000.html`.
3. Anatomy HUD → `auto-label`.
4. Compare visible label count to `min_labels`/`max_labels` in `f000.expected.json`.

## Determinism
Re-run `atl fuzz gen --seed {seed} --count {count}` with the same flags.
Every `f*.html` and `f*.expected.json` is byte-identical across runs.
Only `index.json` (timestamp, run_id) and the run directory name differ.
"""


def generate_corpus(
    seed: int,
    count: int,
    out_base: Path,
    run_id: str | None = None,
) -> Path:
    """Generate `count` fuzz files under `out_base/<run_id>/`.

    Returns the run directory. Deterministic per (seed, count).
    """
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")

    effective_run_id = run_id or f"{_now_iso()}-seed{seed}"
    run_dir = out_base / effective_run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    manifest_entries: list[dict] = []

    for i in range(count):
        file_id = f"f{i:03d}"
        shape_names = _pick_shapes_for_file(rng)
        fragments = _build_fragments(rng, i, shape_names)
        html = envelope.wrap(file_id, seed, fragments)
        expected = _build_expected(file_id, seed, fragments)

        _atomic_write(run_dir / f"{file_id}.html", html)
        _atomic_write(
            run_dir / f"{file_id}.expected.json",
            json.dumps(expected, indent=2, ensure_ascii=False) + "\n",
        )
        manifest_entries.append({
            "file_id": file_id,
            "shapes": shape_names,
            "min_labels": expected["min_labels"],
            "max_labels": expected["max_labels"],
        })

    index = {
        "run_id": effective_run_id,
        "seed": seed,
        "count": count,
        "created_at": _now_iso(),
        "generator_version": "atl-fuzz@0.1.0",
        "catalog": _catalog(),
        "files": manifest_entries,
    }
    _atomic_write(
        run_dir / "index.json",
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
    )
    _atomic_write(
        run_dir / "README.md",
        _README.format(
            run_id=effective_run_id,
            seed=seed,
            count=count,
            abs_dir=str(run_dir.resolve()).replace("\\", "/"),
        ),
    )
    return run_dir
