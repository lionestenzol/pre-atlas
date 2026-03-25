"""Tests for atlas_config.compute_mode() — single source of truth for mode routing."""

import sys
from pathlib import Path

# Ensure cognitive-sensor is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from atlas_config import compute_mode, ROUTING


class TestComputeMode:
    """Test the three-mode routing decision engine."""

    def test_closure_low_ratio(self):
        """ratio < 15% forces CLOSURE regardless of open loops."""
        mode, risk, build_allowed = compute_mode(10.0, 5)
        assert mode == "CLOSURE"
        assert risk == "HIGH"
        assert build_allowed is False

    def test_closure_high_open_loops(self):
        """open_loops > 20 forces CLOSURE regardless of ratio."""
        mode, risk, build_allowed = compute_mode(80.0, 25)
        assert mode == "CLOSURE"
        assert risk == "HIGH"
        assert build_allowed is False

    def test_closure_both_triggers(self):
        """Both triggers active → still CLOSURE."""
        mode, risk, build_allowed = compute_mode(5.0, 30)
        assert mode == "CLOSURE"
        assert build_allowed is False

    def test_maintenance_mode(self):
        """ratio >= 15% and 10 < open_loops <= 20 → MAINTENANCE."""
        mode, risk, build_allowed = compute_mode(50.0, 15)
        assert mode == "MAINTENANCE"
        assert risk == "MEDIUM"
        assert build_allowed is True

    def test_build_mode(self):
        """ratio >= 15% and open_loops <= 10 → BUILD."""
        mode, risk, build_allowed = compute_mode(72.0, 7)
        assert mode == "BUILD"
        assert risk == "LOW"
        assert build_allowed is True

    def test_boundary_ratio_exactly_15(self):
        """ratio == 15.0 (not less than) with low loops → not CLOSURE."""
        mode, _, _ = compute_mode(15.0, 5)
        assert mode == "BUILD"

    def test_boundary_ratio_just_below_15(self):
        """ratio = 14.9 → CLOSURE."""
        mode, _, _ = compute_mode(14.9, 5)
        assert mode == "CLOSURE"

    def test_boundary_loops_exactly_20(self):
        """open_loops == 20 (not greater) → MAINTENANCE."""
        mode, _, _ = compute_mode(50.0, 20)
        assert mode == "MAINTENANCE"

    def test_boundary_loops_21(self):
        """open_loops == 21 → CLOSURE."""
        mode, _, _ = compute_mode(50.0, 21)
        assert mode == "CLOSURE"

    def test_boundary_loops_exactly_10(self):
        """open_loops == 10 (not greater) → BUILD."""
        mode, _, _ = compute_mode(50.0, 10)
        assert mode == "BUILD"

    def test_boundary_loops_11(self):
        """open_loops == 11 → MAINTENANCE."""
        mode, _, _ = compute_mode(50.0, 11)
        assert mode == "MAINTENANCE"

    def test_zero_state(self):
        """Zero ratio and zero loops → CLOSURE (ratio < 15)."""
        mode, _, build_allowed = compute_mode(0.0, 0)
        assert mode == "CLOSURE"
        assert build_allowed is False

    def test_perfect_state(self):
        """100% ratio and 0 loops → BUILD."""
        mode, risk, build_allowed = compute_mode(100.0, 0)
        assert mode == "BUILD"
        assert risk == "LOW"
        assert build_allowed is True

    def test_routing_thresholds_exist(self):
        """ROUTING dict has all expected keys."""
        assert "closure_ratio_critical" in ROUTING
        assert "open_loops_critical" in ROUTING
        assert "open_loops_caution" in ROUTING
        assert "min_loop_score" in ROUTING
        assert ROUTING["closure_ratio_critical"] == 15.0
        assert ROUTING["open_loops_critical"] == 20
        assert ROUTING["open_loops_caution"] == 10
