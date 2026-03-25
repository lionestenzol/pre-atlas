"""Tests for governor_daily.py — daily governance pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from governor_daily import (
    compute_mode,
    compute_lane_status,
    detect_lane_violations,
    compute_world_changed,
    generate_brief,
)


def make_cognitive_state(open_loops=7, closed=18, ratio=72.0):
    return {
        "closure": {"open": open_loops, "closed": closed, "ratio": ratio},
        "loops": [
            {"convo_id": "1", "title": "Loop A", "score": 20000},
            {"convo_id": "2", "title": "Loop B", "score": 19000},
        ],
    }


def make_idea_registry(execute_now=None, next_up=None):
    return {
        "tiers": {
            "execute_now": execute_now or [],
            "next_up": next_up or [],
        },
        "metadata": {"total_ideas": 5, "tier_breakdown": {"execute_now": 2, "next_up": 1}},
    }


class TestGovernorComputeMode:
    """Test governor's mode computation delegating to atlas_config."""

    def test_build_mode(self):
        state = make_cognitive_state(open_loops=7, ratio=72.0)
        mode, risk, allowed = compute_mode(state, {})
        assert mode == "BUILD"
        assert allowed is True

    def test_closure_mode_low_ratio(self):
        state = make_cognitive_state(ratio=10.0)
        mode, risk, allowed = compute_mode(state, {})
        assert mode == "CLOSURE"
        assert allowed is False

    def test_closure_mode_high_loops(self):
        state = make_cognitive_state(open_loops=25, ratio=50.0)
        mode, _, allowed = compute_mode(state, {})
        assert mode == "CLOSURE"
        assert allowed is False

    def test_maintenance_mode(self):
        state = make_cognitive_state(open_loops=15, ratio=50.0)
        mode, _, _ = compute_mode(state, {})
        assert mode == "MAINTENANCE"

    def test_missing_closure_data(self):
        """Missing closure data defaults to 0 → CLOSURE mode."""
        mode, _, _ = compute_mode({}, {})
        assert mode == "CLOSURE"


class TestComputeLaneStatus:
    def test_returns_two_lanes(self):
        registry = make_idea_registry()
        status = compute_lane_status(registry)
        assert len(status) == 2

    def test_lane_structure(self):
        registry = make_idea_registry()
        status = compute_lane_status(registry)
        for lane in status:
            assert "id" in lane
            assert "name" in lane
            assert "status" in lane
            assert "blocked" in lane


class TestDetectLaneViolations:
    def test_no_violations_empty_registry(self):
        registry = make_idea_registry()
        violations = detect_lane_violations(registry)
        assert violations == []

    def test_detects_third_lane_idea(self):
        registry = make_idea_registry(
            execute_now=[{
                "canonical_title": "Cryptocurrency Trading Bot",
                "status": "idea",
                "priority_score": 50,
            }]
        )
        violations = detect_lane_violations(registry)
        assert len(violations) >= 1
        assert violations[0]["recommendation"] == "park"

    def test_capped_at_five(self):
        ideas = [
            {"canonical_title": f"Unrelated Idea {i}", "status": "idea", "priority_score": 10}
            for i in range(10)
        ]
        registry = make_idea_registry(execute_now=ideas)
        violations = detect_lane_violations(registry)
        assert len(violations) <= 5


class TestComputeWorldChanged:
    def test_returns_bullets(self):
        state = make_cognitive_state()
        bullets = compute_world_changed(state, {}, make_idea_registry())
        assert len(bullets) >= 2
        assert any("Open loops" in b for b in bullets)

    def test_with_classifications(self):
        state = make_cognitive_state()
        classifications = {
            "statistics": {
                "outcome_breakdown": {"looped": 10, "produced": 5, "resolved": 3},
            }
        }
        bullets = compute_world_changed(state, classifications, make_idea_registry())
        assert any("Conversations" in b for b in bullets)


class TestGenerateBrief:
    def test_produces_markdown(self):
        brief = generate_brief(
            mode="BUILD",
            risk="LOW",
            build_allowed=True,
            world_changed=["Open loops: 7, Closure ratio: 72.0%"],
            leverage_moves=["Ship Chapter 1"],
            automation_target="Automate loop closing",
            decisions=[],
            lane_status=[{"name": "Test Lane", "status": "in_progress"}],
        )
        assert "# Daily Brief" in brief
        assert "BUILD" in brief
        assert "Ship Chapter 1" in brief

    def test_closure_mode_brief(self):
        brief = generate_brief(
            mode="CLOSURE",
            risk="HIGH",
            build_allowed=False,
            world_changed=["Open loops: 25"],
            leverage_moves=["Close top loop"],
            automation_target="None",
            decisions=[{"question": "Archive loop X?", "options": ["Yes", "No"], "recommendation": "Yes"}],
            lane_status=[],
        )
        assert "CLOSURE" in brief
        assert "Build allowed: No" in brief
        assert "Archive loop X?" in brief

    def test_guardrails_section(self):
        brief = generate_brief(
            mode="BUILD", risk="LOW", build_allowed=True,
            world_changed=[], leverage_moves=[], automation_target="",
            decisions=[], lane_status=[],
        )
        assert "Guardrails Active" in brief
        assert "Idea moratorium" in brief
