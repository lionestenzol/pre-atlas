"""Cognitive-Sensor client — wraps CLI invocations via subprocess.

Cognitive-sensor has NO HTTP API. All interaction is via:
  - python atlas_cli.py daily|weekly|backlog|briefs|status
  - Reading output files: daily_payload.json, governance_state.json, daily_brief.md
"""
import asyncio
import json
import structlog
from pathlib import Path
from typing import Any

log = structlog.get_logger()

SUBPROCESS_TIMEOUT = 120  # seconds, matches REFRESH_TIMEOUT_MS in governance_daemon.ts


class CognitiveClient:
    """Subprocess-based client for cognitive-sensor pipeline."""

    def __init__(self, sensor_dir: Path):
        self.sensor_dir = Path(sensor_dir)

    async def _run_cli(self, command: str) -> tuple[int, str, str]:
        """Run atlas_cli.py with a command. Returns (returncode, stdout, stderr)."""
        cmd = f"python atlas_cli.py {command}"
        log.info("cognitive_client.run", command=command, cwd=str(self.sensor_dir))

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=str(self.sensor_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=SUBPROCESS_TIMEOUT
            )
            return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            log.error("cognitive_client.timeout", command=command, timeout=SUBPROCESS_TIMEOUT)
            proc.kill()
            return -1, "", f"Timeout after {SUBPROCESS_TIMEOUT}s"

    # --- CLI Commands ---

    async def run_daily(self) -> dict[str, Any]:
        """Run the full daily loop: refresh + governor brief."""
        rc, stdout, stderr = await self._run_cli("daily")
        return {"success": rc == 0, "stdout": stdout, "stderr": stderr}

    async def run_weekly(self) -> dict[str, Any]:
        """Run the full weekly loop: daily + audit + governor packet."""
        rc, stdout, stderr = await self._run_cli("weekly")
        return {"success": rc == 0, "stdout": stdout, "stderr": stderr}

    async def run_backlog(self) -> dict[str, Any]:
        """Run idea pipeline + backlog maintenance."""
        rc, stdout, stderr = await self._run_cli("backlog")
        return {"success": rc == 0, "stdout": stdout, "stderr": stderr}

    async def run_status(self) -> dict[str, Any]:
        """Print system status and file freshness."""
        rc, stdout, stderr = await self._run_cli("status")
        return {"success": rc == 0, "stdout": stdout, "stderr": stderr}

    # --- File Readers ---

    def read_daily_payload(self) -> dict[str, Any]:
        """Read daily_payload.json — minimal mode signal."""
        path = self.sensor_dir / "daily_payload.json"
        if not path.exists():
            return {"error": "daily_payload.json not found"}
        return json.loads(path.read_text(encoding="utf-8"))

    def read_governance_state(self) -> dict[str, Any]:
        """Read governance_state.json — full lane status, violations, targets."""
        path = self.sensor_dir / "governance_state.json"
        if not path.exists():
            return {"error": "governance_state.json not found"}
        return json.loads(path.read_text(encoding="utf-8"))

    def read_daily_brief(self) -> str:
        """Read daily_brief.md — human-readable executive summary."""
        path = self.sensor_dir / "daily_brief.md"
        if not path.exists():
            return "Daily brief not available."
        return path.read_text(encoding="utf-8")

    def read_governance_config(self) -> dict[str, Any]:
        """Read governance_config.json — atlas_config rules exported as JSON."""
        path = self.sensor_dir / "governance_config.json"
        if not path.exists():
            return {"error": "governance_config.json not found"}
        return json.loads(path.read_text(encoding="utf-8"))

    # --- Compound Loop Readers (cross-agent feedback) ---

    def _read_json(self, rel_path: str) -> dict[str, Any]:
        """Read a JSON file relative to sensor_dir. Returns error dict on failure."""
        path = self.sensor_dir / rel_path
        if not path.exists():
            return {"error": f"{rel_path} not found"}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("cognitive_client.read_failed", path=rel_path, error=str(exc))
            return {"error": f"Failed to read {rel_path}: {exc}"}

    def read_life_signals(self) -> dict[str, Any]:
        """Read life_signals.json — multi-domain signals (energy, finance, skills, network)."""
        return self._read_json("life_signals.json")

    def read_completion_stats(self) -> dict[str, Any]:
        """Read completion_stats.json — closure/archive counts for current week."""
        return self._read_json("completion_stats.json")

    def read_closures(self) -> dict[str, Any]:
        """Read closures.json — closure registry with stats and streak tracking."""
        return self._read_json("closures.json")

    def read_auto_actor_log(self) -> dict[str, Any]:
        """Read auto_actor_log.json — last auto_actor run: loops closed, directives executed."""
        return self._read_json("auto_actor_log.json")

    def read_drift_alerts(self) -> dict[str, Any]:
        """Read drift_alerts.json — behavioral drift score and alert list."""
        return self._read_json("drift_alerts.json")

    def read_extracted_value(self) -> dict[str, Any]:
        """Read extracted_value.json — accumulated insights from closed loops."""
        return self._read_json("extracted_value.json")

    def read_classifications(self) -> dict[str, Any]:
        """Read conversation_classifications.json — domain/outcome breakdown per convo."""
        return self._read_json("conversation_classifications.json")

    def read_strategic_priorities(self) -> dict[str, Any]:
        """Read strategic_priorities.json — focus area weights from leverage clusters."""
        return self._read_json("cycleboard/brain/strategic_priorities.json")

    def read_prediction_results(self) -> dict[str, Any]:
        """Read prediction_results.json — MiroFish loop predictions and mode forecast."""
        return self._read_json("cycleboard/brain/prediction_results.json")

    def read_brain_metrics(self, domain: str) -> dict[str, Any]:
        """Read a domain metrics file from cycleboard/brain/ (energy, finance, skills, network)."""
        return self._read_json(f"cycleboard/brain/{domain}_metrics.json")

    def read_idea_registry(self) -> dict[str, Any]:
        """Read idea_registry.json — all ideas across 4 tiers with priority scores."""
        return self._read_json("idea_registry.json")

    def write_compound_state(self, state: dict[str, Any]) -> None:
        """Write compound_state.json to cycleboard/brain/ for CycleBoard consumption."""
        path = self.sensor_dir / "cycleboard" / "brain" / "compound_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.compound_state_written", path=str(path))

    # --- Project Goal Hierarchy ---

    def read_project_goals(self) -> dict[str, Any]:
        """Read project_goals.json — goal-milestone-subtask hierarchy."""
        return self._read_json("project_goals.json")

    def write_project_goals(self, goals: dict[str, Any]) -> None:
        """Write project_goals.json — atomic full-file replacement."""
        path = self.sensor_dir / "project_goals.json"
        path.write_text(json.dumps(goals, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.project_goals_written", path=str(path))

    # --- Skill Registry ---

    def read_skill_registry(self) -> dict[str, Any]:
        """Read skill_registry.json — individual skill tracking with proficiency."""
        return self._read_json("skill_registry.json")

    def write_skill_registry(self, registry: dict[str, Any]) -> None:
        """Write skill_registry.json — atomic full-file replacement."""
        path = self.sensor_dir / "skill_registry.json"
        path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.skill_registry_written", path=str(path))

    # --- Analyst Decisions ---

    def read_analyst_decisions(self) -> dict[str, Any]:
        """Read analyst_decisions.json — autonomous decision log."""
        return self._read_json("analyst_decisions.json")

    def write_analyst_decisions(self, decisions: dict[str, Any]) -> None:
        """Write analyst_decisions.json — atomic full-file replacement."""
        path = self.sensor_dir / "analyst_decisions.json"
        path.write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.analyst_decisions_written", path=str(path))

    # --- Financial Ledger ---

    def read_financial_ledger(self) -> dict[str, Any]:
        """Read financial_ledger.json — transactions, budgets, projections."""
        return self._read_json("financial_ledger.json")

    def write_financial_ledger(self, ledger: dict[str, Any]) -> None:
        """Write financial_ledger.json — atomic full-file replacement."""
        path = self.sensor_dir / "financial_ledger.json"
        path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.financial_ledger_written", path=str(path))

    # --- Network Registry ---

    def read_network_registry(self) -> dict[str, Any]:
        """Read network_registry.json — contacts, interactions, opportunities."""
        return self._read_json("network_registry.json")

    def write_network_registry(self, registry: dict[str, Any]) -> None:
        """Write network_registry.json — atomic full-file replacement."""
        path = self.sensor_dir / "network_registry.json"
        path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.network_registry_written", path=str(path))

    # --- Energy Log ---

    def read_energy_log(self) -> dict[str, Any]:
        """Read energy_log.json — daily energy tracking with trend data."""
        return self._read_json("energy_log.json")

    def write_energy_log(self, log_data: dict[str, Any]) -> None:
        """Write energy_log.json — atomic full-file replacement."""
        path = self.sensor_dir / "energy_log.json"
        path.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.energy_log_written", path=str(path))

    # --- Automation Queue ---

    def read_automation_queue(self) -> dict[str, Any]:
        """Read automation_queue.json — scheduled tasks and execution history."""
        return self._read_json("automation_queue.json")

    def write_automation_queue(self, queue: dict[str, Any]) -> None:
        """Write automation_queue.json — atomic full-file replacement."""
        path = self.sensor_dir / "automation_queue.json"
        path.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.automation_queue_written", path=str(path))

    # --- Risk State ---

    def read_risk_state(self) -> dict[str, Any]:
        """Read risk_state.json — mitigation plans, interference, guardrails."""
        return self._read_json("risk_state.json")

    def write_risk_state(self, state: dict[str, Any]) -> None:
        """Write risk_state.json — atomic full-file replacement."""
        path = self.sensor_dir / "risk_state.json"
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("cognitive_client.risk_state_written", path=str(path))
