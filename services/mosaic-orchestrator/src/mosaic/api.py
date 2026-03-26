"""Mosaic Orchestrator REST API — FastAPI on port 3005."""
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from mosaic.metering.metering import MeteringStore
from mosaic.adapters.claude_adapter import ClaudeAdapter

app = FastAPI(
    title="Mosaic Orchestrator",
    version="0.2.0",
    description="Unified coordination for Pre Atlas platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clients (initialized once)
delta = DeltaClient(config.delta_kernel_url)
cognitive = CognitiveClient(config.cognitive_sensor_dir)
aegis = AegisClient(config.aegis_url, config.aegis_api_key)
mirofish = MirofishClient(config.mirofish_url)
openclaw = OpenClawClient(config.openclaw_url)
festival = FestivalClient()
metering = MeteringStore(config.metering_db_path, config.free_tier_seconds)
claude_adapter = ClaudeAdapter(config.anthropic_api_key, config.ollama_url, config.ollama_model)


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
    """Execute a task via the Claude adapter with metering."""
    from mosaic.adapters.claude_adapter import TaskSpec, TaskPriority

    if metering.is_paused():
        return {"status": "paused", "message": "AI metering is paused"}

    spec = TaskSpec(
        task_id=task_spec.get("task_id", "manual"),
        instructions=task_spec.get("instructions", ""),
        files_context=task_spec.get("files_context", []),
        timeout_seconds=task_spec.get("timeout_seconds", 300),
        priority=TaskPriority(task_spec.get("priority", "normal")),
        use_fallback=task_spec.get("use_fallback", False),
    )
    result = await claude_adapter.execute_task(spec)
    metering.record_usage(result.duration_seconds, result.tokens_used, result.provider, "task_execute")
    return {
        "task_id": result.task_id,
        "success": result.success,
        "output": result.output,
        "duration_seconds": result.duration_seconds,
        "tokens_used": result.tokens_used,
        "provider": result.provider,
        "error": result.error,
    }


@app.post("/api/v1/workflows/daily")
async def trigger_daily():
    """Manually trigger the daily automation loop."""
    result = await run_daily_loop(delta, cognitive)
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


@app.get("/api/v1/metering/usage")
async def metering_usage():
    """Current AI usage stats."""
    usage = metering.get_usage()
    return usage


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
