"""Exhaustive tests for the perception schema (spec §2) and Step 1 invariants."""

from __future__ import annotations

import dataclasses
import json
import re
import typing
from pathlib import Path

import pytest

from perception import (
    VERSION,
    Chapter,
    ChapterResult,
    Element,
    ElementType,
    EvidenceStream,
    PageGraph,
    Signature,
    TextContent,
    perceive,
)
from perception import (
    calibrator,
    chapter_extractor,
    config,
    corrections_log,
    lexicon,
    patterns,
    priors,
    reconciler,
    scanner_adapter,
    text_extractor,
)


# ── ElementType ────────────────────────────────────────────────────────────

def test_element_type_enum_string_roundtrip():
    assert ElementType.NAV == "nav"
    assert ElementType("nav") is ElementType.NAV
    assert ElementType.UNKNOWN == "unknown"


def test_element_type_enum_membership():
    expected = {
        "NAV", "HERO", "CTA", "FEATURE", "PRICING", "FORM", "FOOTER",
        "NAV_LINK", "AUTH_CTA", "LOGO", "HEADING", "SUBHEAD", "BODY",
        "IMAGE", "ICON", "UNKNOWN",
    }
    assert {m.name for m in ElementType} == expected
    assert len(ElementType) == 16


# ── EvidenceStream ─────────────────────────────────────────────────────────

def test_evidence_stream_literal_values():
    args = typing.get_args(EvidenceStream)
    assert set(args) == {
        "scanner_geometry",
        "text_extractor",
        "lexicon",
        "calibrator_repetition",
        "prior_prediction",
        "pattern_match",
        "user_correction",
    }
    assert len(args) == 7


# ── TextContent ────────────────────────────────────────────────────────────

def test_textcontent_required_fields():
    with pytest.raises(TypeError):
        TextContent()  # type: ignore[call-arg]


def test_textcontent_defaults():
    t = TextContent(content="hi", font_size=16.0, font_weight=400)
    assert t.color is None
    assert t.is_aria is False
    assert t.is_alt is False


# ── Signature ──────────────────────────────────────────────────────────────

def test_signature_hash_equality():
    s1 = Signature(
        type="card", rounded_w=20, rounded_h=15, child_count=3,
        child_types=("h2", "p", "button"),
    )
    s2 = Signature(
        type="card", rounded_w=20, rounded_h=15, child_count=3,
        child_types=("h2", "p", "button"),
    )
    assert hash(s1) == hash(s2)
    assert s1 == s2


def test_signature_hash_difference_child_types():
    s1 = Signature(
        type="card", rounded_w=20, rounded_h=15, child_count=3,
        child_types=("h2", "p", "button"),
    )
    s2 = Signature(
        type="card", rounded_w=20, rounded_h=15, child_count=3,
        child_types=("h2", "p", "a"),
    )
    assert hash(s1) != hash(s2)


def test_signature_hash_difference_geometry():
    s1 = Signature(type="card", rounded_w=20, rounded_h=15, child_count=3)
    s2 = Signature(type="card", rounded_w=25, rounded_h=15, child_count=3)
    assert hash(s1) != hash(s2)


def test_signature_child_types_default_is_tuple():
    s = Signature(type="card", rounded_w=10, rounded_h=10, child_count=0)
    assert isinstance(s.child_types, tuple)
    assert s.child_types == ()


def test_signature_usable_as_dict_key():
    sig = Signature(type="card", rounded_w=20, rounded_h=15, child_count=3)
    bucket: dict[Signature, int] = {sig: 1}
    assert bucket[sig] == 1


# ── Element ────────────────────────────────────────────────────────────────

def test_element_minimal_construction():
    e = Element(
        id="e1", type=ElementType.NAV, label="nav",
        x=0.0, y=0.0, w=100.0, h=10.0,
    )
    assert e.id == "e1"
    assert e.type is ElementType.NAV
    assert e.confidence == 0.0
    assert e.inferred is False


def test_element_full_construction():
    sig = Signature(type="card", rounded_w=20, rounded_h=15, child_count=2)
    txt = TextContent(content="Get started", font_size=14.0, font_weight=600)
    e = Element(
        id="e1", type=ElementType.CTA, label="primary cta",
        x=10.0, y=20.0, w=30.0, h=8.0,
        axes=["x_axis_2", "y_row_3"],
        signature=sig,
        repetition_group="rg_abc",
        text=txt,
        confidence=0.85,
        evidence=["scanner_geometry", "lexicon"],
        inferred=False,
        conflicts=["lexicon disagreed: AUTH_CTA"],
        parent_id="p1",
        children_ids=["c1", "c2"],
        pattern_match="hero_stack",
        chapter=2,
        dom_tag="button",
        scanner_id="scanner-42",
    )
    assert e.confidence == 0.85
    assert e.text is txt
    assert e.signature is sig
    assert e.repetition_group == "rg_abc"
    assert e.scanner_id == "scanner-42"


def test_element_default_lists_independent():
    e1 = Element(id="a", type=ElementType.NAV, label="a", x=0, y=0, w=1, h=1)
    e2 = Element(id="b", type=ElementType.NAV, label="b", x=0, y=0, w=1, h=1)
    e1.axes.append("x_axis_0")
    e1.evidence.append("scanner_geometry")
    e1.conflicts.append("note")
    e1.children_ids.append("c1")
    assert e2.axes == []
    assert e2.evidence == []
    assert e2.conflicts == []
    assert e2.children_ids == []


def test_element_field_count():
    """Guard rail: count fields, fail loudly on accidental schema additions (spec §6)."""
    fields = dataclasses.fields(Element)
    assert len(fields) == 21, f"Element field count drift; got {len(fields)}"


def test_element_dataclass_serialization_roundtrip():
    e = Element(
        id="e1", type=ElementType.NAV, label="nav",
        x=0.0, y=0.0, w=100.0, h=10.0,
        evidence=["scanner_geometry"],
    )
    d = dataclasses.asdict(e)
    s = json.dumps(d)
    parsed = json.loads(s)
    assert parsed["id"] == "e1"
    assert parsed["type"] == "nav"
    assert parsed["evidence"] == ["scanner_geometry"]
    assert parsed["axes"] == []
    assert parsed["children_ids"] == []
    assert parsed["confidence"] == 0.0


def test_element_equality_by_value():
    e1 = Element(id="x", type=ElementType.NAV, label="n", x=0, y=0, w=1, h=1)
    e2 = Element(id="x", type=ElementType.NAV, label="n", x=0, y=0, w=1, h=1)
    assert e1 == e2


def test_element_id_required():
    with pytest.raises(TypeError):
        Element(type=ElementType.NAV, label="n", x=0, y=0, w=1, h=1)  # type: ignore[call-arg]


# ── Chapter ────────────────────────────────────────────────────────────────

def test_chapter_required_fields():
    c = Chapter(id=1, title="Hero", desc="top section", element_ids=["e1", "e2"])
    assert c.id == 1
    assert c.element_ids == ["e1", "e2"]


# ── PageGraph ──────────────────────────────────────────────────────────────

def test_pagegraph_construction_empty():
    g = PageGraph(
        url="https://example.com",
        elements=[],
        chapters=[],
        scan_timestamp="2026-04-26T00:00:00+00:00",
        pipeline_version=VERSION,
    )
    assert g.elements == []
    assert g.chapters == []
    assert g.pipeline_version == VERSION


def test_pagegraph_construction_full(sample_element: Element):
    c = Chapter(id=1, title="t", desc="d", element_ids=[sample_element.id])
    g = PageGraph(
        url="https://example.com",
        elements=[sample_element],
        chapters=[c],
        scan_timestamp="2026-04-26T00:00:00+00:00",
        pipeline_version=VERSION,
    )
    assert g.elements[0] is sample_element
    assert g.chapters[0] is c


# ── ChapterResult ──────────────────────────────────────────────────────────

def test_chapter_result_helper():
    r = ChapterResult(elements=[], chapters=[])
    assert r.elements == []
    assert r.chapters == []
    field_names = {f.name for f in dataclasses.fields(ChapterResult)}
    assert field_names == {"elements", "chapters"}


# ── Step 1 done-criteria ──────────────────────────────────────────────────

def test_pipeline_import_smoke():
    """Spec §5 Step 1 done-criterion: from perception.pipeline import perceive must succeed."""
    from perception.pipeline import perceive as p
    assert callable(p)


def test_each_stub_raises_notimplementederror(sample_element: Element):
    """Spec §6: never silently return empty. Every stub raises with step marker."""
    sample_text = TextContent(content="hi", font_size=14.0, font_weight=400)
    cases = [
        (lambda: scanner_adapter.scan("https://x"), "Step 2"),
        (lambda: text_extractor.extract("https://x"), "Step 3"),
        (lambda: calibrator.calibrate([sample_element]), "Step 4"),
        (lambda: lexicon.apply([sample_element], [sample_text]), "Step 5"),
        (lambda: priors.apply([sample_element]), "Step 6"),
        (lambda: patterns.match([sample_element]), "Step 7"),
        (lambda: reconciler.fuse([sample_element], [sample_text]), "Step 8"),
        (lambda: chapter_extractor.extract([sample_element]), "Step 9"),
        (lambda: corrections_log.append({}), "Step 10"),
    ]
    for call, step_marker in cases:
        with pytest.raises(NotImplementedError) as info:
            call()
        msg = str(info.value)
        assert step_marker in msg, (
            f"Expected '{step_marker}' in NotImplementedError msg, got: {msg!r}"
        )


def test_perceive_calls_stubs_in_order(monkeypatch: pytest.MonkeyPatch):
    """Spec §4 ordering must be preserved across all future refactors.

    Also asserts reconciler.fuse receives the right kwargs - kwarg drift in a
    refactor would silently change fusion semantics.
    """
    calls: list[str] = []
    fuse_kwargs: dict = {}

    scanner_out = [
        Element(id="s1", type=ElementType.NAV, label="n", x=0, y=0, w=1, h=1),
    ]
    text_out = [TextContent(content="hi", font_size=14.0, font_weight=400)]

    def fake_scan(url):
        calls.append("scan")
        return scanner_out

    def fake_extract(url):
        calls.append("extract")
        return text_out

    def fake_calibrate(elements):
        calls.append("calibrate")
        return elements

    def fake_lexicon_apply(elements, text_elements):
        calls.append("lexicon.apply")
        return elements

    def fake_priors_apply(elements):
        calls.append("priors.apply")
        return elements

    def fake_patterns_match(elements):
        calls.append("patterns.match")
        return elements

    def fake_reconciler_fuse(*, geometric, text, debug=False):
        calls.append("reconciler.fuse")
        fuse_kwargs["geometric"] = geometric
        fuse_kwargs["text"] = text
        fuse_kwargs["debug"] = debug
        return geometric

    def fake_chapter_extract(elements):
        calls.append("chapter_extractor.extract")
        return ChapterResult(elements=elements, chapters=[])

    monkeypatch.setattr(scanner_adapter, "scan", fake_scan)
    monkeypatch.setattr(text_extractor, "extract", fake_extract)
    monkeypatch.setattr(calibrator, "calibrate", fake_calibrate)
    monkeypatch.setattr(lexicon, "apply", fake_lexicon_apply)
    monkeypatch.setattr(priors, "apply", fake_priors_apply)
    monkeypatch.setattr(patterns, "match", fake_patterns_match)
    monkeypatch.setattr(reconciler, "fuse", fake_reconciler_fuse)
    monkeypatch.setattr(chapter_extractor, "extract", fake_chapter_extract)

    g = perceive("https://example.com", debug=True)
    assert calls == [
        "scan",
        "extract",
        "calibrate",
        "lexicon.apply",
        "priors.apply",
        "patterns.match",
        "reconciler.fuse",
        "chapter_extractor.extract",
    ]
    # reconciler.fuse must receive the exact objects produced upstream.
    assert fuse_kwargs["text"] is text_out
    assert isinstance(fuse_kwargs["geometric"], list)
    assert fuse_kwargs["debug"] is True

    assert isinstance(g, PageGraph)
    assert g.url == "https://example.com"
    assert g.pipeline_version == VERSION


def test_no_silent_exception_handlers():
    """Spec §6: do not silently catch exceptions during development.

    Catches:
      - bare `except:`
      - `except <anything>: \\n pass` including `as e`, tuple-excepts, multi-line
    """
    src_root = Path(__file__).resolve().parent.parent / "src" / "perception"
    silent_pass = re.compile(r"except[^:\n]*:\s*\n\s*pass\b", re.MULTILINE)
    bare_except = re.compile(r"except\s*:")
    offenders: list[str] = []
    for py in src_root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if silent_pass.search(text) or bare_except.search(text):
            offenders.append(str(py))
    assert not offenders, f"Silent exception handlers found in: {offenders}"


def test_corrections_jsonl_exists_empty():
    """Sentinel file ships in the package under src/perception/corrections.jsonl."""
    path = config.CORRECTIONS_PATH
    assert path.exists(), f"corrections.jsonl missing at {path}"
    assert path.stat().st_size == 0, "corrections.jsonl must start empty"


def test_config_paths_anchored_to_package():
    """Path constants resolve relative to the installed package, not cwd."""
    pkg_root = Path(config.__file__).resolve().parent
    assert config.CORRECTIONS_PATH == pkg_root / "corrections.jsonl"
    assert config.LEXICON_PATH == pkg_root / "lexicon.json"
    assert config.PRIORS_PATH == pkg_root / "priors.json"
    assert config.DEBUG_DIR == pkg_root / "debug"


def test_lexicon_priors_files_ship_with_package():
    """Package data files exist next to the source after pip install -e ."""
    assert config.LEXICON_PATH.exists()
    assert config.PRIORS_PATH.exists()


def test_config_version_present():
    assert config.VERSION == "0.1.0"
    assert VERSION == config.VERSION


def test_config_evidence_weights_cover_all_streams():
    """EVIDENCE_WEIGHTS must have a key for every EvidenceStream literal."""
    weight_keys = set(config.EVIDENCE_WEIGHTS.keys())
    stream_values = set(typing.get_args(EvidenceStream))
    assert weight_keys == stream_values, (
        f"EVIDENCE_WEIGHTS keys do not match EvidenceStream literal: "
        f"missing={stream_values - weight_keys}, extra={weight_keys - stream_values}"
    )
