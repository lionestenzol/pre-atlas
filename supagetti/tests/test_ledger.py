"""
Tests for core/ledger.py's bearings-ported additions: the findings category
tally, the honest source split, and the governance tax.
"""
from __future__ import annotations

import json

import pytest

from core import case_manager, ledger


def test_classify_ext_buckets_match_bearings():
    assert ledger._classify_ext(".py") == "product"
    assert ledger._classify_ext(".ts") == "product"
    assert ledger._classify_ext(".md") == "docs"
    assert ledger._classify_ext(".json") == "data"
    assert ledger._classify_ext(".png") == "other"
    assert ledger._classify_ext("(no extension)") == "other"


@pytest.fixture
def case_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(case_manager, "CASES_DIR", tmp_path)
    d = tmp_path / "CASE_0001_test_project"
    (d / "source").mkdir(parents=True)
    (d / "source" / "placeholder.txt").write_text("x", encoding="utf-8")

    case_manager.write_json(d / "intake.json", {
        "case_id": "CASE_0001", "project_name": "test_project", "source_type": "folder",
        "user_claim": "a claim", "user_pain": "a pain", "desired_outcome": "an outcome",
        "audience": "someone", "privacy_level": "internal", "scope_limit": None,
        "source_reference": None, "created_at": "2026-01-01T00:00:00Z",
    })

    scan = {
        "case_id": "CASE_0001", "generated_at": "2026-01-01T00:00:00Z",
        "started_at": "2026-01-01T00:00:00Z",
        "file_count": 6, "dir_count": 1, "total_size_bytes": 100,
        "extension_counts": {".py": 3, ".md": 2, ".json": 1},
        "languages_detected": ["Python"],
        "manifests": {k: {"detected": False, "confidence": "high"} for k in (
            "package_json", "requirements_txt", "pyproject_toml", "dockerfile",
            "ci_config", "readme", "license_file", "tests_dir", "env_example", "gitignore",
        )},
        "largest_files": [], "top_level_entries": [],
        "symbolic_compression": {
            "files_included": 0, "raw_tokens_est": 0, "compressed_tokens_est": 0,
            "token_yield": 0, "compression_ratio": 0.0, "symbolic_nodes": [],
        },
        "warnings": [],
    }
    case_manager.write_json(d / "scan.json", scan)

    findings = {
        "case_id": "CASE_0001", "generated_at": "2026-01-01T00:00:00Z",
        "findings": [
            {
                "id": "F-001", "title": "A", "category": "Structural", "severity": "info",
                "confidence": "high", "evidence": ["e"], "plain_language": "p",
                "technical_finding": "t", "why_it_matters": "w", "recommended_next_action": "n",
            },
            {
                "id": "F-002", "title": "B", "category": "Structural", "severity": "low",
                "confidence": "high", "evidence": ["e"], "plain_language": "p",
                "technical_finding": "t", "why_it_matters": "w", "recommended_next_action": "n",
            },
            {
                "id": "F-003", "title": "C", "category": "Security", "severity": "high",
                "confidence": "medium", "evidence": ["e"], "plain_language": "p",
                "technical_finding": "t", "why_it_matters": "w", "recommended_next_action": "n",
            },
        ],
    }
    case_manager.write_json(d / "findings.json", findings)
    return d


def test_source_split_and_category_tally(case_dir):
    case_manager.write_json(case_dir / "governor_report.json", {
        "case_id": "CASE_0001", "generated_at": "2026-01-01T00:00:00Z",
        "status": "approved", "checklist": [], "blocking_reasons": [],
        "summary": "All clean.", "verification": [
            {"finding_id": "F-001", "checks_run": 2, "verified": 2, "contradictions": [], "grounded": True},
        ],
    })
    (case_dir / "report.md").write_text("# report", encoding="utf-8")

    status = ledger.run_ledger("CASE_0001")
    assert status.status == "ok"

    entry = json.loads((case_dir / "ledger_entry.json").read_text())

    assert entry["source_split"] == {"product": 3, "docs": 2, "data": 1, "other": 0}

    by_cat = {c["category"]: c["count"] for c in entry["findings_by_category"]}
    assert by_cat == {"Structural": 2, "Security": 1}

    tax = entry["governance_tax"]
    assert tax["shipped"] is True
    assert tax["checks_run"] == 2
    assert tax["checks_verified"] == 2
    assert tax["blocked_reasons"] == []


def test_governance_tax_reflects_blocked_effort_with_no_shipped_report(case_dir):
    case_manager.write_json(case_dir / "governor_report.json", {
        "case_id": "CASE_0001", "generated_at": "2026-01-01T00:00:00Z",
        "status": "blocked", "checklist": [],
        "blocking_reasons": ["CONTRADICTED (code-verified): finding F-003 claims \"x\" but y."],
        "summary": "Blocked due to a contradiction.", "verification": [
            {"finding_id": "F-003", "checks_run": 1, "verified": 0,
             "contradictions": [{"claim": "x", "kind": "path", "verdict": "contradicted", "detail": "y"}],
             "grounded": False},
        ],
    })
    # no report.md written — report generation was blocked

    status = ledger.run_ledger("CASE_0001")
    assert status.status == "ok"

    entry = json.loads((case_dir / "ledger_entry.json").read_text())
    tax = entry["governance_tax"]
    assert tax["shipped"] is False
    assert tax["checks_run"] == 1
    assert tax["checks_verified"] == 0
    assert len(tax["blocked_reasons"]) == 1
