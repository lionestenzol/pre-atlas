# triangulation

Verification module for an existing DOM-based UI scraper. Cross-validates auto-labels using three independent signals (DOM heuristic, spatial geometry, visual similarity) via quorum vote.

Sidecar to the anatomy-extension daemon. Per-element verdict: `confirmed | flagged | rejected`.

## Status

Phase A shipped: schema, `spatial.py` fully implemented (pure numpy), `consensus.py` fully implemented (handles cold-start visual=None), `visual.ReferenceLibrary` fully implemented. `visual.Embedder.embed` and `api.py` are Phase B/C stubs.

## Run

```bash
python -m pip install -e ".[dev]"

python -c "from triangulation import verify, ReferenceLibrary; print('OK')"
python -m pytest -v tests/
```

For the visual signal (Phase B):
```bash
python -m pip install -e ".[dev,visual]"
python -m pytest -v -m integration tests/
```

For the FastAPI sidecar (Phase C):
```bash
python -m pip install -e ".[dev,api]"
python -m triangulation.api
```

## Layout

- `src/triangulation/schema.py` — `ElementInput`, `SpatialSignal`, `VisualSignal`, `VerifyResult` dataclasses.
- `src/triangulation/spatial.py` — pure numpy. 5 functions per brief: `find_alignment_groups`, `check_spacing_regularity`, `check_label_consistency`, `check_containment`, `score_element`.
- `src/triangulation/visual.py` — SigLIP-2 `Embedder` (Phase B stub), `ReferenceLibrary` (full).
- `src/triangulation/consensus.py` — `aggregate(element, spatial, visual)` -> `VerifyResult`. Quorum vote.
- `src/triangulation/api.py` — Phase C FastAPI surface.
- `src/triangulation/config.py` — tolerances + signal weights.

## Constraints (per brief)

No video. No Gemini. No ChromaDB. No external APIs. No training. No frontend. Tolerances are placeholders pending Phase D real-data calibration — do not tune until 100+ real elements have been seen.
