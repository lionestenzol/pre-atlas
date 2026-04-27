# perception

Deterministic webpage-perception pipeline. Reads a URL or DOM, fuses geometric scanning with text extraction, applies UI priors and pattern recognition, and emits a unified `Element` graph with chapters, confidence scores, and provenance.

Spec: see Bruke's build doc. Build log: `BUILD_LOG.md`.

## Status

Step 1 of 12 — schema + project skeleton. All modules are stubs that raise `NotImplementedError`. Real logic lands in subsequent steps.

## Run

```bash
python -m pip install -e ".[dev]"
python -c "from perception.pipeline import perceive; print('OK')"
pytest -v tests/
```

## Layout

- `src/perception/schema.py` - canonical `Element` dataclass + `Chapter`, `PageGraph`, `Signature`, `TextContent`, `ChapterResult`, `ElementType`, `EvidenceStream`. Frozen at spec §2.
- `src/perception/pipeline.py` - `perceive(url)` orchestrator (verbatim spec §4).
- `src/perception/config.py` - constants. No magic numbers in modules.
- `src/perception/{scanner_adapter, text_extractor, calibrator, lexicon, priors, patterns, reconciler, chapter_extractor, corrections_log}.py` - stubs.
- `tests/test_schema.py` - exhaustive schema coverage (Step 1).
- `corrections.jsonl` - append-only correction log. Committed empty.
- `lexicon.json`, `priors.json` - data files. Empty until Steps 5/6.

## Constraints

Per spec §6: no ML, no LLM in pipeline; deps limited to stdlib + dataclasses + pytest + numpy; schema is fixed; do not modify the existing scanner/annotator/viewer; do not silently catch exceptions.
