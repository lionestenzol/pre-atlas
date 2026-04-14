"""Mosaic Orchestrator REST API — FastAPI on port 3005."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from mosaic.config import config
from mosaic.clients.delta_client import DeltaClient
from mosaic.clients.cognitive_client import CognitiveClient
from mosaic.clients.aegis_client import AegisClient
from mosaic.clients.mirofish_client import MirofishClient
from mosaic.clients.openclaw_client import OpenClawClient
from mosaic.clients.festival_client import FestivalClient
from mosaic.workflows.daily_loop import run_daily_loop
from mosaic.workflows.stall_detector import detect_stalls
from mosaic.workflows.idea_simulation import run_idea_to_simulation
from mosaic.workflows.compound_loop import run_compound_loop
from mosaic.metering.metering import MeteringStore
from mosaic.adapters.claude_adapter import ClaudeAdapter
from mosaic.queue.client import QueueClient
from mosaic.queue.publisher import NatsPublisher
from mosaic.queue.executor import EmbeddedExecutor

log = structlog.get_logger()

# Clients (initialized once)
delta = DeltaClient(config.delta_kernel_url, api_key=config.delta_api_key)
cognitive = CognitiveClient(config.cognitive_sensor_dir)
aegis = AegisClient(config.aegis_url, config.aegis_api_key)
mirofish = MirofishClient(config.mirofish_url)
openclaw = OpenClawClient(config.openclaw_url)
festival = FestivalClient()
metering = MeteringStore(config.metering_db_path, config.free_tier_seconds)
claude_adapter = ClaudeAdapter(config.anthropic_api_key, config.ollama_url, config.ollama_model)

# Queue components (initialized on startup if USE_QUEUE=true)
queue_client = QueueClient()
nats_publisher = NatsPublisher()
executor: EmbeddedExecutor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the queue system."""
    global executor
    if config.use_queue:
        log.info("queue.startup", instance_id=config.executor_instance_id)
        await queue_client.connect(config.postgres_dsn)
        await nats_publisher.connect(config.nats_url)
        executor = EmbeddedExecutor(
            queue=queue_client,
            publisher=nats_publisher,
            adapter=claude_adapter,
            metering=metering,
            instance_id=config.executor_instance_id,
        )
        await executor.start()
    yield
    if config.use_queue:
        if executor:
            await executor.stop()
        await nats_publisher.close()
        await queue_client.close()
        log.info("queue.shutdown")


app = FastAPI(
    title="Mosaic Orchestrator",
    version="0.3.0",
    description="Unified coordination for Pre Atlas platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health():
    """Health check — reports connectivity to all subsystems."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
    }


@app.get("/api/v1/status")
async def system_status():
    """Full system status — mode, festival, simulations, metering."""
    # Delta-kernel state
    dk_state = await delta.get_unified_state()

    # Festival status
    fest_status = await festival.status()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": dk_state.get("mode", "UNKNOWN"),
        "risk": dk_state.get("risk", "UNKNOWN"),
        "build_allowed": dk_state.get("build_allowed", False),
        "open_loops": dk_state.get("open_loops", 0),
        "festival": fest_status,
    }


@app.post("/api/v1/tasks/execute")
async def execute_task(task_spec: dict):
    """Emit a task to delta for daemon execution."""
    if metering.is_paused():
        return {"status": "paused", "message": "AI metering is paused"}

    _priority_int = {"low": 0, "normal": 1, "high": 2, "critical": 3}
    result = await delta.request_work({
        "type": "ai",
        "title": task_spec.get("task_id", "manual-task"),
        "timeout_ms": task_spec.get("timeout_seconds", 300) * 1000,
        "metadata": {
            "cmd": "@WORK",
            "inputs": {
                "instructions": task_spec.get("instructions", ""),
                "files_context": task_spec.get("files_context", []),
            },
            "source": "orchestrator",
            "intent": "execute_task",
            "priority": _priority_int.get(task_spec.get("priority", "normal"), 1),
        }
    })
    return {"status": "emitted", "job_id": result.get("job_id"), "admission": result.get("status")}


@app.post("/api/v1/workflows/daily")
async def trigger_daily():
    """Manually trigger the daily automation loop (includes compound feedback)."""
    result = await run_daily_loop(delta, cognitive, nats_publisher, openclaw)
    return result


@app.post("/api/v1/workflows/stall-check")
async def trigger_stall_check():
    """Run the stall detector and notify if stalled."""
    result = await detect_stalls(cognitive, openclaw)
    return result


@app.post("/api/v1/workflows/idea-simulation")
async def trigger_idea_simulation():
    """Run the idea-to-simulation pipeline."""
    result = await run_idea_to_simulation(cognitive, mirofish, openclaw)
    return result


@app.post("/api/v1/workflows/compound")
async def trigger_compound_loop():
    """Run the compound feedback loop — cross-domain signal computation."""
    result = await run_compound_loop(cognitive, delta, nats_publisher, openclaw)
    return result


@app.get("/api/v1/compound/state")
async def get_compound_state():
    """Return the latest compound state from brain/compound_state.json."""
    import json
    path = cognitive.sensor_dir / "cycleboard" / "brain" / "compound_state.json"
    if not path.exists():
        return {"error": "compound_state.json not found — run /api/v1/workflows/compound first"}
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/v1/queue/stats")
async def queue_stats():
    """Execution queue statistics."""
    if not config.use_queue:
        return {"enabled": False, "stats": {}}
    stats = await queue_client.stats()
    return {"enabled": True, "stats": stats}


@app.get("/api/v1/queue/jobs/{job_id}")
async def queue_job(job_id: str):
    """Get status and result for a specific queued job."""
    if not config.use_queue:
        return {"error": "Queue not enabled"}
    job = await queue_client.get_job(job_id)
    if job is None:
        return {"error": "Job not found"}
    return job


@app.get("/api/v1/metering/usage")
async def metering_usage():
    """Current AI usage stats."""
    usage = metering.get_usage()
    return usage


# --- Project Goal Hierarchy ---


@app.get("/api/v1/project/goals")
async def get_project_goals():
    """Return goal hierarchy with live-computed progress percentages."""
    from mosaic.workflows.compound_loops.project_progress import (
        compute_goal_progress,
        compute_milestone_progress,
    )

    goals_data = cognitive.read_project_goals()
    if "error" in goals_data:
        return {"error": goals_data["error"]}

    # Compute live progress for each goal and milestone
    for goal in goals_data.get("goals", []):
        goal["progress_pct"] = round(compute_goal_progress(goal), 1)
        for ms in goal.get("milestones", []):
            ms["progress_pct"] = round(compute_milestone_progress(ms), 1)

    return goals_data


@app.post("/api/v1/project/goals/{goal_id}/decompose")
async def decompose_goal(goal_id: str):
    """Emit a goal decomposition task to delta for daemon execution."""
    goals_data = cognitive.read_project_goals()
    if "error" in goals_data:
        return {"error": goals_data["error"]}

    goal = next((g for g in goals_data["goals"] if g["goal_id"] == goal_id), None)
    if not goal:
        return {"error": f"Goal {goal_id} not found"}
    if goal.get("milestones"):
        return {"error": f"Goal {goal_id} already has milestones"}

    prompt = f"""Decompose this project goal into milestones and subtasks.

Goal: {goal['title']}
Ship Criteria: {goal.get('ship_criteria', 'Not specified')}

Return a JSON array of milestones. Each milestone has:
- "title": string
- "subtasks": array of objects with "title", "tags", "depends_on_titles"

Return 3-5 milestones, each with 2-5 subtasks. Order by execution sequence.
Return ONLY the JSON array."""

    result = await delta.request_work({
        "type": "ai",
        "title": f"decompose-goal-{goal_id}",
        "metadata": {
            "cmd": "@WORK",
            "inputs": {
                "instructions": prompt,
                "goal_id": goal_id,
                "output_handler": "goal_decompose",
            },
            "source": "orchestrator",
            "intent": "decompose_goal",
            "priority": 1,
            "constraints": {"timeout_seconds": 120, "max_cost_usd": 0.50},
        }
    })
    return {"status": "emitted", "goal_id": goal_id, "job_id": result.get("job_id")}


@app.post("/api/v1/project/subtasks/{subtask_id}/complete")
async def complete_subtask(subtask_id: str):
    """Mark a subtask as done and cascade progress up the hierarchy."""
    goals_data = cognitive.read_project_goals()
    if "error" in goals_data:
        return {"error": goals_data["error"]}

    # Find the subtask
    found = False
    target_goal = None
    target_milestone = None
    for goal in goals_data["goals"]:
        for ms in goal.get("milestones", []):
            for st in ms.get("subtasks", []):
                if st["subtask_id"] == subtask_id:
                    if st["status"] == "done":
                        return {"error": f"Subtask {subtask_id} is already done"}
                    st["status"] = "done"
                    st["completed_at"] = datetime.now(timezone.utc).isoformat()
                    found = True
                    target_goal = goal
                    target_milestone = ms
                    break
            if found:
                break
        if found:
            break

    if not found:
        return {"error": f"Subtask {subtask_id} not found"}

    # Auto-advance milestone if all subtasks done
    from mosaic.workflows.compound_loops.project_progress import (
        compute_milestone_progress,
        compute_goal_progress,
    )

    ms_progress = compute_milestone_progress(target_milestone)
    if ms_progress >= 100.0:
        target_milestone["status"] = "done"
        # Activate next pending milestone
        milestones = target_goal.get("milestones", [])
        sorted_ms = sorted(milestones, key=lambda m: m.get("order", 0))
        for ms in sorted_ms:
            if ms["status"] == "pending":
                ms["status"] = "active"
                break

    # Auto-complete goal if all milestones done
    goal_progress = compute_goal_progress(target_goal)
    if goal_progress >= 100.0:
        target_goal["status"] = "done"

    goals_data["generated_at"] = datetime.now(timezone.utc).isoformat()
    cognitive.write_project_goals(goals_data)

    return {
        "subtask_id": subtask_id,
        "status": "done",
        "milestone_id": target_milestone["milestone_id"],
        "milestone_progress": round(ms_progress, 1),
        "milestone_status": target_milestone["status"],
        "goal_id": target_goal["goal_id"],
        "goal_progress": round(goal_progress, 1),
        "goal_status": target_goal["status"],
    }


# --- Skill Registry ---


@app.get("/api/v1/skills/registry")
async def get_skill_registry():
    """Return the full skill registry with live proficiency levels."""
    from mosaic.workflows.compound_loops.skill_progression import (
        compute_skill_health_signals,
    )

    registry = cognitive.read_skill_registry()
    if "error" in registry:
        return {"error": registry["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_skill_health_signals(registry, now_iso)

    return {
        **registry,
        "health": signals,
    }


@app.post("/api/v1/skills/{skill_id}/log")
async def log_skill_usage(skill_id: str):
    """Manually log skill usage (exercises, courses, client work)."""
    from mosaic.workflows.compound_loops.skill_progression import apply_skill_usage

    registry = cognitive.read_skill_registry()
    if "error" in registry:
        return {"error": registry["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    updated = apply_skill_usage(
        registry,
        {skill_id: 1},
        f"manual_{now_iso[:10]}",
        now_iso,
    )
    cognitive.write_skill_registry(updated)

    skill = updated["skills"].get(skill_id, {})
    return {
        "skill_id": skill_id,
        "usage_count": skill.get("usage_count", 0),
        "proficiency": skill.get("proficiency", "novice"),
        "category": skill.get("category", "emerging"),
    }


@app.get("/api/v1/skills/recommendations")
async def get_skill_recommendations():
    """Which skills to develop next, based on gap analysis and lane alignment."""
    from mosaic.workflows.compound_loops.skill_progression import (
        recommend_next_skills,
        compute_skill_health_signals,
    )

    registry = cognitive.read_skill_registry()
    if "error" in registry:
        return {"error": registry["error"]}

    # Get lane tags from project goals
    lane_tags: list[str] = []
    goals_data = cognitive.read_project_goals()
    if "error" not in goals_data:
        for goal in goals_data.get("goals", []):
            for ms in goal.get("milestones", []):
                for st in ms.get("subtasks", []):
                    lane_tags.extend(st.get("tags", []))

    recs = recommend_next_skills(registry, lane_tags)
    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_skill_health_signals(registry, now_iso)

    return {
        "recommendations": recs,
        "mastery_count": signals["mastery_count"],
        "growth_count": signals["growth_count"],
        "stagnant_skills": signals["stagnant_skills"],
    }


# --- Energy Log ---


@app.get("/api/v1/energy/log")
async def get_energy_log():
    """Energy log with trend analysis."""
    from mosaic.workflows.compound_loops.energy_engine import compute_energy_health_signals

    log_data = cognitive.read_energy_log()
    if "error" in log_data:
        return {"error": log_data["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_energy_health_signals(log_data, now_iso)

    return {
        **log_data,
        "health": signals,
    }


@app.post("/api/v1/energy/log")
async def log_energy_entry(data: dict):
    """Log a daily energy entry."""
    from mosaic.workflows.compound_loops.energy_engine import log_energy_entry

    log_data = cognitive.read_energy_log()
    if "error" in log_data:
        log_data = {"schema_version": "1.0.0", "entries": []}

    energy_level = data.get("energy_level")
    if energy_level is None:
        return {"error": "energy_level is required"}

    now_iso = datetime.now(timezone.utc).isoformat()
    date = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    updated = log_energy_entry(
        log_data, date,
        energy_level=int(energy_level),
        mental_load=int(data.get("mental_load", 5)),
        sleep_quality=int(data.get("sleep_quality", 3)),
        sleep_hours=float(data.get("sleep_hours", 0)),
        exercise_minutes=int(data.get("exercise_minutes", 0)),
        notes=data.get("notes", ""),
        now_iso=now_iso,
    )
    cognitive.write_energy_log(updated)

    return {
        "date": date,
        "energy_level": energy_level,
        "entries_count": len(updated["entries"]),
    }


@app.get("/api/v1/energy/trends")
async def get_energy_trends():
    """7-day energy trends with burnout detection."""
    from mosaic.workflows.compound_loops.energy_engine import compute_energy_health_signals

    log_data = cognitive.read_energy_log()
    if "error" in log_data:
        return {"error": log_data["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_energy_health_signals(log_data, now_iso)

    return {
        "trends": signals["trends"],
        "burnout": signals["burnout"],
        "red_alert": signals["red_alert"],
        "recovery_suggestions": signals["recovery_suggestions"],
    }


# --- Automation Queue ---


@app.get("/api/v1/automation/queue")
async def get_automation_queue():
    """Full automation queue with health signals."""
    from mosaic.workflows.compound_loops.automation_engine import compute_automation_health_signals

    queue = cognitive.read_automation_queue()
    if "error" in queue:
        return {"error": queue["error"]}

    energy = cognitive.read_brain_metrics("energy")
    drift = cognitive.read_drift_alerts()
    energy_level = energy.get("energy_level", 50) if "error" not in energy else 50
    drift_score = drift.get("drift_score", 0) if "error" not in drift else 0

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_automation_health_signals(queue, now_iso, energy_level, drift_score)

    return {
        **queue,
        "health": signals,
    }


@app.post("/api/v1/automation/tasks")
async def add_automation_task(data: dict):
    """Add a scheduled task to the automation queue."""
    from mosaic.workflows.compound_loops.automation_engine import add_task

    queue = cognitive.read_automation_queue()
    if "error" in queue:
        queue = {"schema_version": "1.0.0", "tasks": [], "execution_history": []}

    action = data.get("action")
    if not action:
        return {"error": "action is required"}

    now_iso = datetime.now(timezone.utc).isoformat()
    updated, task_id = add_task(
        queue,
        task_type=data.get("type", "recurring"),
        action=action,
        schedule=data.get("schedule", "daily"),
        conditions=data.get("conditions"),
        now_iso=now_iso,
    )
    cognitive.write_automation_queue(updated)

    return {
        "task_id": task_id,
        "action": action,
        "type": data.get("type", "recurring"),
        "schedule": data.get("schedule", "daily"),
    }


@app.get("/api/v1/automation/due")
async def get_automation_due():
    """Tasks that are due for execution."""
    from mosaic.workflows.compound_loops.automation_engine import compute_due_tasks, evaluate_conditions

    queue = cognitive.read_automation_queue()
    if "error" in queue:
        return {"error": queue["error"]}

    energy = cognitive.read_brain_metrics("energy")
    drift = cognitive.read_drift_alerts()
    energy_level = energy.get("energy_level", 50) if "error" not in energy else 50
    drift_score = drift.get("drift_score", 0) if "error" not in drift else 0

    now_iso = datetime.now(timezone.utc).isoformat()
    due = compute_due_tasks(queue, now_iso)

    results = []
    for t in due:
        can_run, reason = evaluate_conditions(t, energy_level, drift_score)
        results.append({
            "task_id": t["id"],
            "action": t["action"],
            "hours_overdue": t.get("hours_overdue", 0),
            "can_run": can_run,
            "block_reason": reason if not can_run else None,
        })

    return {
        "due_count": len(due),
        "ready": sum(1 for r in results if r["can_run"]),
        "blocked": sum(1 for r in results if not r["can_run"]),
        "tasks": results,
    }


@app.post("/api/v1/automation/tasks/{task_id}/run")
async def run_automation_task(task_id: str):
    """Manually trigger execution of a scheduled task."""
    from mosaic.workflows.compound_loops.automation_engine import log_execution

    queue = cognitive.read_automation_queue()
    if "error" in queue:
        return {"error": queue["error"]}

    task = next((t for t in queue.get("tasks", []) if t["id"] == task_id), None)
    if not task:
        return {"error": f"Task {task_id} not found"}

    now_iso = datetime.now(timezone.utc).isoformat()
    updated = log_execution(
        queue, task_id,
        success=True,
        output=f"Manually triggered: {task['action']}",
        duration_seconds=0,
        now_iso=now_iso,
    )
    cognitive.write_automation_queue(updated)

    return {
        "task_id": task_id,
        "action": task["action"],
        "status": "executed",
        "next_run_at": next(
            (t["next_run_at"] for t in updated["tasks"] if t["id"] == task_id),
            None,
        ),
    }


# --- Network Registry ---


@app.get("/api/v1/network/registry")
async def get_network_registry():
    """Full contact registry with health signals."""
    from mosaic.workflows.compound_loops.network_engine import compute_network_health_signals

    registry = cognitive.read_network_registry()
    if "error" in registry:
        return {"error": registry["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_network_health_signals(registry, now_iso)

    return {
        **registry,
        "health": signals,
    }


@app.post("/api/v1/network/contacts")
async def add_network_contact(data: dict):
    """Add a contact to the network registry."""
    from mosaic.workflows.compound_loops.network_engine import add_contact

    registry = cognitive.read_network_registry()
    if "error" in registry:
        registry = {"schema_version": "1.0.0", "contacts": {}, "interactions": [], "opportunities": [], "outreach_queue": []}

    name = data.get("name")
    if not name:
        return {"error": "name is required"}

    now_iso = datetime.now(timezone.utc).isoformat()
    updated, contact_id = add_contact(
        registry,
        name=name,
        title=data.get("title", ""),
        company=data.get("company", ""),
        email=data.get("email", ""),
        status=data.get("status", "cold"),
        tags=data.get("tags"),
        next_follow_up=data.get("next_follow_up"),
        notes=data.get("notes", ""),
        now_iso=now_iso,
    )
    cognitive.write_network_registry(updated)

    return {
        "contact_id": contact_id,
        "name": name,
        "status": data.get("status", "cold"),
        "total_contacts": len(updated["contacts"]),
    }


@app.post("/api/v1/network/interactions")
async def log_network_interaction(data: dict):
    """Log an interaction with a contact."""
    from mosaic.workflows.compound_loops.network_engine import log_interaction

    registry = cognitive.read_network_registry()
    if "error" in registry:
        return {"error": registry["error"]}

    contact_id = data.get("contact_id")
    interaction_type = data.get("type", "email")
    if not contact_id:
        return {"error": "contact_id is required"}
    if contact_id not in registry.get("contacts", {}):
        return {"error": f"Contact {contact_id} not found"}

    now_iso = datetime.now(timezone.utc).isoformat()
    updated, ix_id = log_interaction(
        registry,
        contact_id=contact_id,
        interaction_type=interaction_type,
        outcome=data.get("outcome", "neutral"),
        notes=data.get("notes", ""),
        date=data.get("date", ""),
        now_iso=now_iso,
    )
    cognitive.write_network_registry(updated)

    contact = updated["contacts"].get(contact_id, {})
    return {
        "interaction_id": ix_id,
        "contact_id": contact_id,
        "contact_status": contact.get("status"),
        "next_follow_up": contact.get("next_follow_up"),
    }


@app.get("/api/v1/network/outreach-due")
async def get_outreach_due():
    """Contacts needing follow-up."""
    from mosaic.workflows.compound_loops.network_engine import compute_outreach_due

    registry = cognitive.read_network_registry()
    if "error" in registry:
        return {"error": registry["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    due = compute_outreach_due(registry.get("contacts", {}), now_iso)

    return {
        "due_count": len(due),
        "contacts": due,
    }


@app.get("/api/v1/network/opportunities")
async def get_network_opportunities():
    """Matched opportunities from Loop 2 leverage analysis."""
    from mosaic.workflows.compound_loops.network_engine import match_opportunities_to_contacts

    registry = cognitive.read_network_registry()
    if "error" in registry:
        return {"error": registry["error"]}

    priorities = cognitive.read_strategic_priorities()
    if "error" in priorities:
        return {"opportunities": [], "message": "No strategic priorities available"}

    clusters = priorities.get("top_clusters", [])
    opp_labels = [
        f"{c.get('label', '')}: {c.get('revenue_tag', '')}"
        for c in clusters
        if c.get("revenue_tag") in ("productizable_system", "infrastructure_build", "consulting_ready")
    ]

    matches = match_opportunities_to_contacts(opp_labels, registry.get("contacts", {}))

    return {
        "opportunity_count": len(opp_labels),
        "matched_contacts": matches,
    }


# --- Financial Ledger ---


@app.get("/api/v1/finance/ledger")
async def get_financial_ledger():
    """Full ledger with computed summaries."""
    from mosaic.workflows.compound_loops.finance_engine import compute_finance_health_signals

    ledger = cognitive.read_financial_ledger()
    if "error" in ledger:
        return {"error": ledger["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    signals = compute_finance_health_signals(ledger, now_iso)

    return {
        **ledger,
        "health": signals,
    }


@app.post("/api/v1/finance/transactions")
async def log_transaction(txn: dict):
    """Log a financial transaction.

    Body: { amount, category, description?, recurring?, date?, tags? }
    Positive amount = income, negative = expense.
    """
    from mosaic.workflows.compound_loops.finance_engine import add_transaction

    ledger = cognitive.read_financial_ledger()
    if "error" in ledger:
        return {"error": ledger["error"]}

    amount = txn.get("amount")
    category = txn.get("category", "other")
    if amount is None:
        return {"error": "amount is required"}

    now_iso = datetime.now(timezone.utc).isoformat()
    updated, txn_id = add_transaction(
        ledger,
        amount=float(amount),
        category=category,
        description=txn.get("description", ""),
        recurring=txn.get("recurring", False),
        date=txn.get("date", ""),
        tags=txn.get("tags"),
        now_iso=now_iso,
    )
    cognitive.write_financial_ledger(updated)

    return {
        "transaction_id": txn_id,
        "amount": amount,
        "category": category,
        "balance": updated["balance"],
    }


@app.get("/api/v1/finance/summary")
async def get_finance_summary():
    """Monthly summary with budget variance."""
    from mosaic.workflows.compound_loops.finance_engine import (
        compute_monthly_summary,
        compute_budget_variance,
    )

    ledger = cognitive.read_financial_ledger()
    if "error" in ledger:
        return {"error": ledger["error"]}

    now = datetime.now(timezone.utc)
    current_month = f"{now.year}-{now.month:02d}"

    summary = compute_monthly_summary(ledger.get("transactions", []), current_month)
    variance = compute_budget_variance(
        ledger.get("budgets", {}),
        ledger.get("transactions", []),
        current_month,
    )

    return {
        "month": current_month,
        "summary": summary,
        "budget_variance": variance,
        "balance": ledger.get("balance", 0),
    }


@app.get("/api/v1/finance/forecast")
async def get_finance_forecast():
    """12-month cash flow projection."""
    from mosaic.workflows.compound_loops.finance_engine import compute_cash_flow_projection

    ledger = cognitive.read_financial_ledger()
    if "error" in ledger:
        return {"error": ledger["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    projections = compute_cash_flow_projection(
        ledger.get("transactions", []),
        ledger.get("balance", 0),
        months_ahead=12,
        now_iso=now_iso,
    )

    return {
        "balance": ledger.get("balance", 0),
        "projections": projections,
    }


@app.get("/api/v1/finance/alerts")
async def get_finance_alerts():
    """Active financial alerts."""
    from mosaic.workflows.compound_loops.finance_engine import detect_alerts

    ledger = cognitive.read_financial_ledger()
    if "error" in ledger:
        return {"error": ledger["error"]}

    now_iso = datetime.now(timezone.utc).isoformat()
    alerts = detect_alerts(ledger, now_iso)

    return {
        "alert_count": len(alerts),
        "alerts": alerts,
    }


# --- Risk Mitigation ---


@app.get("/api/v1/risk/state")
async def get_risk_state():
    """Current risk state with mitigation plans, interference, guardrails."""
    state = cognitive.read_risk_state()
    if "error" in state:
        return {"error": state["error"]}
    return state


@app.get("/api/v1/risk/mitigation")
async def get_risk_mitigation():
    """Active mitigation plans with recovery actions."""
    state = cognitive.read_risk_state()
    if "error" in state:
        return {"error": state["error"]}

    plans = state.get("active_plans", [])
    recovery = state.get("recovery_target")

    return {
        "plan_count": len(plans),
        "plans": plans,
        "recovery_target": recovery,
        "guardrails": state.get("guardrails"),
    }


@app.get("/api/v1/risk/interference")
async def get_risk_interference():
    """Detected personal interference patterns."""
    state = cognitive.read_risk_state()
    if "error" in state:
        return {"error": state["error"]}

    interference = state.get("interference_signals", [])

    return {
        "signal_count": len(interference),
        "signals": interference,
    }


# --- Analyst Decisions ---


@app.get("/api/v1/analyst/decisions")
async def get_analyst_decisions():
    """Recent decision log with rationale."""
    data = cognitive.read_analyst_decisions()
    if "error" in data:
        return {"error": data["error"]}
    return data


@app.get("/api/v1/analyst/pending")
async def get_analyst_pending():
    """Escalated decisions awaiting human review."""
    data = cognitive.read_analyst_decisions()
    if "error" in data:
        return {"error": data["error"]}

    pending = [d for d in data.get("decisions", []) if d.get("outcome") == "escalated"]
    return {
        "pending_count": len(pending),
        "decisions": pending,
    }


@app.post("/api/v1/analyst/decisions/{decision_id}/approve")
async def approve_analyst_decision(decision_id: str):
    """Approve an escalated decision."""
    data = cognitive.read_analyst_decisions()
    if "error" in data:
        return {"error": data["error"]}

    found = False
    for d in data.get("decisions", []):
        if d["decision_id"] == decision_id:
            if d["outcome"] != "escalated":
                return {"error": f"Decision {decision_id} is not pending (outcome={d['outcome']})"}
            d["outcome"] = "approved"
            d["approved_at"] = datetime.now(timezone.utc).isoformat()
            found = True
            break

    if not found:
        return {"error": f"Decision {decision_id} not found"}

    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    cognitive.write_analyst_decisions(data)

    return {"decision_id": decision_id, "outcome": "approved"}


@app.post("/api/v1/analyst/reprioritize")
async def trigger_reprioritization():
    """Trigger manual reprioritization based on current compound state."""
    from mosaic.workflows.compound_loops.analyst_engine import (
        evaluate_priority_adjustments,
        compute_analyst_signals,
    )

    # Read current state
    priorities = cognitive.read_strategic_priorities()
    if "error" in priorities:
        return {"error": "Strategic priorities not available"}

    # Read latest compound state for domain scores
    import json as json_mod
    compound_path = cognitive.sensor_dir / "cycleboard" / "brain" / "compound_state.json"
    if not compound_path.exists():
        return {"error": "compound_state.json not found — run compound loop first"}

    compound = json_mod.loads(compound_path.read_text(encoding="utf-8"))
    domain_scores = compound.get("domain_scores", {})
    drift = cognitive.read_drift_alerts()

    now_iso = datetime.now(timezone.utc).isoformat()
    decisions = evaluate_priority_adjustments(priorities, domain_scores, drift, now_iso)
    signals = compute_analyst_signals(decisions)

    # Append to decision log
    data = cognitive.read_analyst_decisions()
    if "error" in data:
        data = {"schema_version": "1.0.0", "decisions": [], "stats": {}}

    data["decisions"] = (data.get("decisions", []) + decisions)[-100:]
    data["stats"] = signals
    data["generated_at"] = now_iso
    cognitive.write_analyst_decisions(data)

    return {
        "decisions": decisions,
        "signals": signals,
    }


@app.post("/api/v1/metering/pause")
async def metering_pause():
    """Toggle pause/resume AI processing."""
    currently_paused = metering.is_paused()
    if currently_paused:
        metering.resume()
        return {"paused": False, "message": "AI metering resumed"}
    else:
        metering.pause()
        return {"paused": True, "message": "AI metering paused"}
