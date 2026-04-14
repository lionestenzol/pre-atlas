"""
AtlasAgent — Unified runtime interface for the Atlas governance stack.

Wraps all existing pipelines into a single class with four entry points:
  run_daily()          — full daily loop (refresh + governor brief)
  run_weekly()         — full weekly loop (daily + audit + governor packet)
  maintain_backlog()   — idea pipeline + backlog maintenance
  generate_briefs_only() — governor briefs without upstream refresh

Does NOT redesign anything. Calls existing scripts via subprocess
in the same order they already run. All autonomy level 2 agents only
mutate internal state (JSON files, SQLite DB, markdown reports).
No external side effects.
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

from atlas_config import NORTH_STAR, TARGETS, ACTIVE_LANES, AGENTS, AutonomyLevel


BASE = Path(__file__).parent.resolve()


class AtlasAgent:
    """Unified runtime interface for the Atlas governance stack."""

    def __init__(self):
        self.base = BASE
        self.python = sys.executable
        self._log = []

    # ── Public API ──────────────────────────────────────────

    def run_daily(self):
        """Full daily loop.

        Phase 1 (AI-FOR-ITSELF, Level 2): Refresh all state
          loops.py -> completion_stats.py -> export_cognitive_state.py
          -> route_today.py -> export_daily_payload.py

        Phase 2 (AI-FOR-ITSELF, Level 2): Wire dashboards
          wire_cycleboard.py -> reporter.py -> build_dashboard.py

        Phase 3 (AI-FOR-YOU, Level 1): Generate daily brief
          governor_daily.py -> daily_brief.md + governance_state.json
        """
        self._banner("ATLAS DAILY LOOP")
        total_start = time.time()

        # Phase 1: Ingest & analyze
        self._phase("Phase 1: Ingest & Analyze State")
        self._run("loops.py", "Open loop detection")
        self._run("completion_stats.py", "Completion statistics")
        self._run("export_cognitive_state.py", "Export cognitive state")
        self._run("route_today.py", "Route today's mode")
        self._run("export_daily_payload.py", "Export daily payload")

        # Phase 2: Wire dashboards
        self._phase("Phase 2: Wire Dashboards")
        self._run("wire_cycleboard.py", "Wire CycleBoard")
        self._run("reporter.py", "State history reporter")
        self._run("build_dashboard.py", "Build dashboard")

        # Phase 3: Governor brief
        self._phase("Phase 3: Governor Daily Brief")
        self._run("governor_daily.py", "Governor daily pipeline")

        elapsed = time.time() - total_start
        self._footer("DAILY LOOP COMPLETE", elapsed, [
            "daily_brief.md",
            "governance_state.json",
            "dashboard.html",
        ])

    def run_weekly(self):
        """Full weekly loop.

        Phase 1: Run daily loop (fresh state)
        Phase 2: Behavioral audit (classifier + synthesizer)
        Phase 3: Weekly governor packet
        """
        self._banner("ATLAS WEEKLY LOOP")
        total_start = time.time()

        # Phase 1: Daily loop for latest state
        self._phase("Phase 1: Daily Loop (fresh state)")
        # Inline the daily steps instead of calling run_daily.py
        # to avoid double-printing and keep control
        self._run("loops.py", "Open loop detection")
        self._run("completion_stats.py", "Completion statistics")
        self._run("export_cognitive_state.py", "Export cognitive state")
        self._run("route_today.py", "Route today's mode")
        self._run("export_daily_payload.py", "Export daily payload")
        self._run("wire_cycleboard.py", "Wire CycleBoard")
        self._run("reporter.py", "State history reporter")
        self._run("build_dashboard.py", "Build dashboard")
        self._run("governor_daily.py", "Governor daily pipeline")

        # Phase 2: Behavioral audit
        self._phase("Phase 2: Behavioral Audit")
        self._run("agent_classifier_convo.py", "Conversation classifier")
        self._run("agent_synthesizer.py", "Behavioral audit synthesizer")

        # Phase 3: Weekly governor packet
        self._phase("Phase 3: Governor Weekly Packet")
        self._run("governor_weekly.py", "Governor weekly pipeline")

        elapsed = time.time() - total_start
        self._footer("WEEKLY LOOP COMPLETE", elapsed, [
            "daily_brief.md",
            "governance_state.json",
            "BEHAVIORAL_AUDIT.md",
            "weekly_governor_packet.md",
        ])

    def maintain_backlog(self):
        """Backlog maintenance: re-run idea pipeline + audit.

        Phase 1: Full idea intelligence pipeline
          excavator -> deduplicator -> classifier -> orchestrator -> reporter

        Phase 2: Conversation classifier (update classifications)

        All Level 2 — mutates only internal JSON/MD files.
        """
        self._banner("ATLAS BACKLOG MAINTENANCE")
        total_start = time.time()

        # Phase 1: Idea pipeline
        self._phase("Phase 1: Idea Intelligence Pipeline")
        self._run("agent_excavator.py", "Idea excavator")
        self._run("agent_deduplicator.py", "Idea deduplicator")
        self._run("agent_classifier.py", "Idea classifier")
        self._run("agent_orchestrator.py", "Idea orchestrator")
        self._run("agent_reporter.py", "Idea reporter")

        # Phase 2: Update conversation classifications
        self._phase("Phase 2: Update Classifications")
        self._run("agent_classifier_convo.py", "Conversation classifier")

        elapsed = time.time() - total_start
        self._footer("BACKLOG MAINTENANCE COMPLETE", elapsed, [
            "idea_registry.json",
            "IDEA_REGISTRY.md",
            "conversation_classifications.json",
        ])

    def generate_briefs_only(self):
        """Generate governor briefs from existing state. No upstream refresh.

        Reads whatever state currently exists on disk and generates:
        - daily_brief.md (governor daily)
        - weekly_governor_packet.md (governor weekly)

        Fast — no embedding computation, no DB queries.
        """
        self._banner("ATLAS BRIEFS ONLY")
        total_start = time.time()

        self._phase("Generating Briefs")
        self._run("governor_daily.py", "Governor daily brief")
        self._run("governor_weekly.py", "Governor weekly packet")

        elapsed = time.time() - total_start
        self._footer("BRIEFS GENERATED", elapsed, [
            "daily_brief.md",
            "weekly_governor_packet.md",
        ])

    def status(self):
        """Print current system status from config."""
        print("=" * 60)
        print("ATLAS SYSTEM STATUS")
        print("=" * 60)
        print(f"\nNorth Star: {NORTH_STAR['weekly']}")
        print(f"Active Lanes: {len(ACTIVE_LANES)} / {TARGETS['max_active_lanes']}")
        for lane in ACTIVE_LANES:
            print(f"  - {lane['name']} [{lane['status']}]")
        print(f"Idea Moratorium: {'ON' if TARGETS['idea_moratorium'] else 'OFF'}")
        print(f"Max Research: {TARGETS['max_research_minutes']} min")
        print(f"Build Blocks: {TARGETS['daily_work_blocks']}x {TARGETS['min_build_minutes']} min")

        # Check for existing state files
        print(f"\nState Files:")
        for name in [
            "cognitive_state.json", "governance_state.json",
            "idea_registry.json", "conversation_classifications.json",
            "daily_brief.md", "weekly_governor_packet.md",
        ]:
            path = self.base / name
            if path.exists():
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                age = datetime.now() - mtime
                hours = age.total_seconds() / 3600
                freshness = "fresh" if hours < 1 else f"{hours:.0f}h ago"
                print(f"  [OK]   {name} ({freshness})")
            else:
                print(f"  [MISS] {name}")

        # Registered agents
        print(f"\nRegistered Agents: {len(AGENTS)}")
        for name, spec in AGENTS.items():
            level = AutonomyLevel(spec["autonomy"]).name
            print(f"  - {name}: {level} ({spec['mode']})")

    # ── Internal helpers ────────────────────────────────────

    def _run(self, script, description, retries=2):
        """Run a script via subprocess with retry. Skip if not found."""
        script_path = self.base / script
        if not script_path.exists():
            print(f"  [SKIP] {script} not found")
            self._log.append({"script": script, "status": "skipped"})
            return False

        print(f"  [{description}] ...", end="", flush=True)
        start = time.time()
        for attempt in range(retries + 1):
            try:
                subprocess.check_call(
                    [self.python, str(script_path)],
                    cwd=str(self.base),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                elapsed = time.time() - start
                print(f" done ({elapsed:.1f}s)")
                self._log.append({"script": script, "status": "ok", "elapsed": elapsed})
                return True
            except subprocess.CalledProcessError as e:
                if attempt < retries:
                    print(f" retrying ({attempt + 1}/{retries})...", end="", flush=True)
                    time.sleep(3)
                    continue
                elapsed = time.time() - start
                stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
                print(f" FAILED ({elapsed:.1f}s)")
                if stderr:
                    lines = stderr.strip().split("\n")
                    for line in lines[-3:]:
                        print(f"    {line}")
                self._log.append({"script": script, "status": "failed", "error": stderr[-200:]})
                return False
        return False

    def _banner(self, title):
        """Print section banner."""
        self._log = []
        print()
        print("=" * 60)
        print(f"  {title}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)

    def _phase(self, name):
        """Print phase header."""
        print(f"\n>> {name}")

    def _footer(self, title, elapsed, outputs):
        """Print completion footer."""
        ok = sum(1 for e in self._log if e["status"] == "ok")
        failed = sum(1 for e in self._log if e["status"] == "failed")
        skipped = sum(1 for e in self._log if e["status"] == "skipped")

        print(f"\n{'=' * 60}")
        print(f"  {title} -- {elapsed:.1f}s")
        print(f"  Steps: {ok} ok, {failed} failed, {skipped} skipped")
        print(f"  Outputs:")
        for o in outputs:
            path = self.base / o
            status = "OK" if path.exists() else "MISSING"
            print(f"    [{status}] {o}")
        print("=" * 60)
