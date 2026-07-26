"""Mode simulator — deterministic 'what if' simulation using real atlas_config thresholds."""
import json
import structlog
from dataclasses import dataclass, field

from mirofish.config import config

log = structlog.get_logger()

# Import the real routing thresholds from atlas_config
# These are the exact values that govern the actual system
ROUTING = {
    "closure_ratio_critical": 15.0,
    "open_loops_critical": 20,
    "open_loops_caution": 10,
    "closure_quality_critical": 30.0,
}


def compute_mode(closure_ratio: float, open_loops: int, closure_quality: float = 100.0) -> tuple[str, str, bool]:
    """Mirror of atlas_config.compute_mode() — single source of truth for mode routing.

    Returns: (mode, risk, build_allowed)
    """
    if closure_quality < ROUTING["closure_quality_critical"]:
        return "CLOSURE", "HIGH", False
    if closure_ratio < ROUTING["closure_ratio_critical"] or open_loops > ROUTING["open_loops_critical"]:
        return "CLOSURE", "HIGH", False
    elif open_loops > ROUTING["open_loops_caution"]:
        return "MAINTENANCE", "MEDIUM", True
    else:
        return "BUILD", "LOW", True


@dataclass
class Action:
    type: str       # close_loop, archive_loop, start_new
    target_id: str  # convo_id or topic name
    label: str = ""


@dataclass
class ModeSimulation:
    current_mode: str
    current_risk: str
    current_build_allowed: bool
    current_metrics: dict
    projected_mode: str
    projected_risk: str
    projected_build_allowed: bool
    projected_metrics: dict
    actions_applied: list[Action]
    transitions: list[str]
    mode_changed: bool


class ModeSimulator:
    """Simulate mode transitions by applying hypothetical actions to current state."""

    def __init__(self):
        self._state: dict | None = None

    def _load_state(self) -> dict:
        """Load current cognitive state from cognitive-sensor."""
        if self._state is not None:
            return self._state

        try:
            data = json.loads(config.cognitive_state_path.read_text(encoding="utf-8"))
            closure = data.get("closure", {})
            self._state = {
                "open_loops": closure.get("open", 0),
                "closed": closure.get("closed", 0),
                "truly_closed": closure.get("truly_closed", 0),
                "archived": closure.get("archived", 0),
                "closure_ratio": closure.get("ratio", 0.0),
                "closure_quality": closure.get("closure_quality", 100.0),
            }
            return self._state
        except Exception as e:
            log.error("mode_simulator.state_load_failed", error=str(e))
            return {
                "open_loops": 0, "closed": 0, "truly_closed": 0,
                "archived": 0, "closure_ratio": 0.0, "closure_quality": 100.0,
            }

    def simulate(self, actions: list[dict]) -> ModeSimulation:
        """Apply hypothetical actions and compute projected mode.

        Each action: {"type": "close_loop"|"archive_loop", "target_id": "convo_id"}
        """
        state = self._load_state()

        # Current state
        current_mode, current_risk, current_build = compute_mode(
            state["closure_ratio"], state["open_loops"], state["closure_quality"]
        )
        current_metrics = {
            "open_loops": state["open_loops"],
            "closure_ratio": round(state["closure_ratio"], 2),
            "closure_quality": round(state["closure_quality"], 2),
            "truly_closed": state["truly_closed"],
            "archived": state["archived"],
        }

        # Apply actions
        projected = dict(state)
        applied = []
        transitions = []

        for action_dict in actions:
            action_type = action_dict.get("type", "")
            target = action_dict.get("target_id", "")

            if action_type == "close_loop":
                projected["open_loops"] = max(0, projected["open_loops"] - 1)
                projected["truly_closed"] += 1
                projected["closed"] += 1
                applied.append(Action(type="close_loop", target_id=target, label=f"Close loop {target}"))

            elif action_type == "archive_loop":
                projected["open_loops"] = max(0, projected["open_loops"] - 1)
                projected["archived"] += 1
                projected["closed"] += 1
                applied.append(Action(type="archive_loop", target_id=target, label=f"Archive loop {target}"))

        # Recompute ratios
        finished = projected["closed"] + projected["archived"]
        if finished > 0:
            projected["closure_ratio"] = (projected["truly_closed"] / finished) * 100
            projected["closure_quality"] = (projected["truly_closed"] / max(1, projected["truly_closed"] + projected["archived"])) * 100
        else:
            projected["closure_ratio"] = 0.0
            projected["closure_quality"] = 100.0

        # Compute projected mode
        proj_mode, proj_risk, proj_build = compute_mode(
            projected["closure_ratio"], projected["open_loops"], projected["closure_quality"]
        )

        projected_metrics = {
            "open_loops": projected["open_loops"],
            "closure_ratio": round(projected["closure_ratio"], 2),
            "closure_quality": round(projected["closure_quality"], 2),
            "truly_closed": projected["truly_closed"],
            "archived": projected["archived"],
        }

        # Describe transitions
        if current_mode != proj_mode:
            transitions.append(f"{current_mode} → {proj_mode}")
        if current_risk != proj_risk:
            transitions.append(f"Risk: {current_risk} → {proj_risk}")
        if not current_build and proj_build:
            transitions.append("BUILD mode unlocked — new work allowed")

        # Explain what changed
        for key in ["open_loops", "closure_ratio", "closure_quality"]:
            if current_metrics[key] != projected_metrics[key]:
                transitions.append(
                    f"{key}: {current_metrics[key]} → {projected_metrics[key]}"
                )

        return ModeSimulation(
            current_mode=current_mode,
            current_risk=current_risk,
            current_build_allowed=current_build,
            current_metrics=current_metrics,
            projected_mode=proj_mode,
            projected_risk=proj_risk,
            projected_build_allowed=proj_build,
            projected_metrics=projected_metrics,
            actions_applied=applied,
            transitions=transitions,
            mode_changed=current_mode != proj_mode,
        )

    def find_exit_path(self) -> dict:
        """Find the minimum actions needed to exit CLOSURE mode."""
        state = self._load_state()
        current_mode, _, _ = compute_mode(
            state["closure_ratio"], state["open_loops"], state["closure_quality"]
        )

        if current_mode != "CLOSURE":
            return {"current_mode": current_mode, "actions_needed": 0, "message": "Not in CLOSURE mode."}

        # Try closing loops one at a time until we exit CLOSURE
        test_state = dict(state)
        closes_needed = 0

        for i in range(50):  # Safety limit
            test_state["open_loops"] = max(0, test_state["open_loops"] - 1)
            test_state["truly_closed"] += 1
            test_state["closed"] += 1

            finished = test_state["closed"] + test_state["archived"]
            if finished > 0:
                test_state["closure_ratio"] = (test_state["truly_closed"] / finished) * 100
                test_state["closure_quality"] = (
                    test_state["truly_closed"] / max(1, test_state["truly_closed"] + test_state["archived"])
                ) * 100

            closes_needed += 1
            mode, _, build = compute_mode(
                test_state["closure_ratio"], test_state["open_loops"], test_state["closure_quality"]
            )
            if mode != "CLOSURE":
                return {
                    "current_mode": current_mode,
                    "exit_mode": mode,
                    "closes_needed": closes_needed,
                    "projected_metrics": {
                        "closure_ratio": round(test_state["closure_ratio"], 2),
                        "closure_quality": round(test_state["closure_quality"], 2),
                        "open_loops": test_state["open_loops"],
                    },
                    "build_unlocked": build,
                    "message": f"Close {closes_needed} loops (truly close, don't archive) to reach {mode} mode.",
                }

        return {
            "current_mode": current_mode,
            "closes_needed": -1,
            "message": "Cannot exit CLOSURE mode with loop closures alone. Closure quality is too low.",
        }
