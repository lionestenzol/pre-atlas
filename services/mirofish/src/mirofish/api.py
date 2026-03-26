"""MiroFish REST API — FastAPI on port 3003."""
import asyncio
import structlog
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mirofish.config import config
from mirofish.swarm.store import SimulationStore
from mirofish.swarm.personality import PersonalityGenerator
from mirofish.swarm.simulator import SimulationRunner, SimulationConfig
from mirofish.reports.builder import ReportBuilder
from mirofish.reports.export import to_json, to_markdown
from mirofish.graph.ingester import DocumentIngester

log = structlog.get_logger()

app = FastAPI(
    title="MiroFish",
    version="0.1.0",
    description="Swarm simulation engine for the Mosaic platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared instances
store = SimulationStore()
personality_gen = PersonalityGenerator()
runner = SimulationRunner(store=store)
report_builder = ReportBuilder()


class SimulationRequest(BaseModel):
    topic: str
    agent_count: int = 20
    tick_count: int = 10
    document_text: str | None = None


@app.get("/api/v1/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "service": "mirofish",
    }


async def _run_simulation(sim_id: str, req: SimulationRequest):
    """Background task: run the full simulation pipeline."""
    try:
        # Ingest document if provided
        if req.document_text:
            ingester = DocumentIngester()
            try:
                await ingester.ingest_document(req.document_text)
            except Exception as e:
                log.warning("api.ingest_failed", error=str(e))
            finally:
                await ingester.close()

        # Generate agent personalities
        agents = await personality_gen.generate(
            topic=req.topic,
            count=req.agent_count,
        )

        # Run simulation
        sim_config = SimulationConfig(
            topic=req.topic,
            agents=agents,
            tick_count=req.tick_count,
            document_context=req.document_text or "",
        )
        result = await runner.run(sim_config, simulation_id=sim_id)

        # Generate report
        report = await report_builder.build(result)
        store.save_report(result.simulation_id, report)

        log.info("api.simulation_complete", simulation_id=result.simulation_id)
    except Exception as e:
        log.error("api.simulation_failed", simulation_id=sim_id, error=str(e))
        store.fail_simulation(sim_id, str(e))


@app.post("/api/v1/simulations")
async def start_simulation(req: SimulationRequest, background_tasks: BackgroundTasks):
    """Start a new simulation in the background."""
    import uuid
    sim_id = str(uuid.uuid4())

    # Pre-create in store so it shows up immediately
    store.create_simulation(
        simulation_id=sim_id,
        topic=req.topic,
        agent_count=req.agent_count,
        tick_count=req.tick_count,
        agents=[],
    )

    background_tasks.add_task(_run_simulation, sim_id, req)

    return {
        "simulation_id": sim_id,
        "status": "started",
        "topic": req.topic,
        "agent_count": req.agent_count,
        "tick_count": req.tick_count,
    }


@app.get("/api/v1/simulations")
async def list_simulations():
    """List all simulations."""
    return {"simulations": store.list_simulations()}


@app.get("/api/v1/simulations/{simulation_id}")
async def get_simulation(simulation_id: str, from_tick: int = Query(0, ge=0)):
    """Get simulation detail with tick data. Use from_tick for incremental polling."""
    sim = store.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    ticks = store.get_ticks(simulation_id, from_tick=from_tick)
    sim["ticks"] = ticks
    return sim


@app.get("/api/v1/simulations/{simulation_id}/report")
async def get_report(simulation_id: str):
    """Get the generated report for a completed simulation."""
    sim = store.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if sim["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Simulation status is '{sim['status']}', not 'completed'")
    if not sim.get("report"):
        raise HTTPException(status_code=404, detail="Report not yet generated")
    return sim["report"]


@app.delete("/api/v1/simulations/{simulation_id}")
async def delete_simulation(simulation_id: str):
    """Delete a simulation and all its data."""
    sim = store.get_simulation(simulation_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    store.delete_simulation(simulation_id)
    return {"status": "deleted", "simulation_id": simulation_id}
