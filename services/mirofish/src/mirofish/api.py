"""MiroFish REST API — prediction engine for conversation analysis."""
import structlog
from dataclasses import asdict
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mirofish.config import config
from mirofish.ingest_state import load_state
from mirofish.graph.neo4j_client import Neo4jClient
from mirofish.graph.ingester import ConversationIngester
from mirofish.prediction.insight_engine import InsightEngine
from mirofish.prediction.loop_predictor import LoopPredictor
from mirofish.prediction.pattern_detector import PatternDetector
from mirofish.prediction.mode_simulator import ModeSimulator

log = structlog.get_logger()

app = FastAPI(
    title="MiroFish",
    version="0.2.0",
    description="Conversation prediction engine — real data, deterministic algorithms, no fake agents",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared instances
neo4j = Neo4jClient()
ingester = ConversationIngester(neo4j=neo4j)
insight_engine = InsightEngine(neo4j=neo4j)
mode_simulator = ModeSimulator()


# ── Health ───────────────────────────────────────────────────

@app.get("/api/v1/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.2.0",
        "service": "mirofish",
        "engine": "prediction",
    }


# ── Ingestion ────────────────────────────────────────────────

class IngestRequest(BaseModel):
    batch_size: int = 50
    force: bool = False
    build_edges: bool = False


_ingest_running = False


async def _run_ingest(req: IngestRequest):
    global _ingest_running
    _ingest_running = True
    try:
        result = await ingester.ingest_batch(batch_size=req.batch_size, force=req.force)
        log.info("api.ingest_complete", **result)

        if req.build_edges:
            log.info("api.building_similarity_edges")
            await ingester.build_similarity_edges()
            log.info("api.building_temporal_edges")
            await ingester.build_temporal_edges()
    except Exception as e:
        log.error("api.ingest_failed", error=str(e))
    finally:
        _ingest_running = False


@app.post("/api/v1/ingest")
async def start_ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    """Trigger incremental conversation ingestion."""
    if _ingest_running:
        return {"status": "already_running", "message": "Ingestion is already in progress."}

    background_tasks.add_task(_run_ingest, req)
    state = load_state()
    return {
        "status": "started",
        "batch_size": req.batch_size,
        "force": req.force,
        "current_progress": state.total_ingested,
    }


@app.get("/api/v1/ingest/status")
async def ingest_status():
    """Get ingestion progress."""
    state = load_state()
    return {
        "running": _ingest_running,
        "total_ingested": state.total_ingested,
        "last_convo_index": state.last_convo_index,
        "last_run": state.last_run,
        "topics_created": state.topics_created,
        "similarity_edges_built": state.similarity_edges_built,
        "temporal_edges_built": state.temporal_edges_built,
    }


# ── Predictions ──────────────────────────────────────────────

@app.get("/api/v1/predictions")
async def get_predictions():
    """Full daily insights — loop predictions, patterns, mode forecast, top actions."""
    try:
        insights = await insight_engine.get_daily_insights()
        return asdict(insights)
    except Exception as e:
        log.error("api.predictions_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/predictions/loop/{convo_id}")
async def get_loop_prediction(convo_id: str):
    """Prediction for a specific open loop."""
    predictor = LoopPredictor(neo4j)
    pred = await predictor.predict(convo_id)
    if not pred:
        raise HTTPException(status_code=404, detail=f"No prediction available for conversation {convo_id}")
    return {
        "convo_id": pred.convo_id,
        "title": pred.title,
        "probabilities": pred.probabilities,
        "most_likely": pred.most_likely,
        "confidence": pred.confidence,
        "evidence": pred.evidence,
        "similar_conversations": pred.similar_conversations[:5],
    }


# ── Patterns ─────────────────────────────────────────────────

@app.get("/api/v1/patterns")
async def get_patterns():
    """All detected behavioral patterns."""
    detector = PatternDetector(neo4j)
    patterns = await detector.detect_all()
    return {
        "pattern_count": len(patterns),
        "patterns": [
            {
                "pattern_id": p.pattern_id,
                "type": p.type,
                "description": p.description,
                "confidence": p.confidence,
                "evidence": p.evidence,
                "data": p.data,
            }
            for p in patterns
        ],
    }


# ── Mode Simulation ──────────────────────────────────────────

class SimulateRequest(BaseModel):
    actions: list[dict]  # [{"type": "close_loop", "target_id": "143"}, ...]


@app.post("/api/v1/simulate")
async def simulate_mode(req: SimulateRequest):
    """Simulate mode transitions with hypothetical actions."""
    sim = mode_simulator.simulate(req.actions)
    return {
        "current_mode": sim.current_mode,
        "current_risk": sim.current_risk,
        "current_build_allowed": sim.current_build_allowed,
        "current_metrics": sim.current_metrics,
        "projected_mode": sim.projected_mode,
        "projected_risk": sim.projected_risk,
        "projected_build_allowed": sim.projected_build_allowed,
        "projected_metrics": sim.projected_metrics,
        "actions_applied": [asdict(a) for a in sim.actions_applied],
        "transitions": sim.transitions,
        "mode_changed": sim.mode_changed,
    }


@app.get("/api/v1/simulate/exit-path")
async def get_exit_path():
    """Find minimum actions to exit CLOSURE mode."""
    return mode_simulator.find_exit_path()


# ── Graph ────────────────────────────────────────────────────

@app.get("/api/v1/graph/stats")
async def graph_stats():
    """Neo4j graph statistics — node counts, edge counts, top topics."""
    try:
        return await neo4j.get_graph_stats()
    except Exception as e:
        log.error("api.graph_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/graph/topic/{topic_name}")
async def topic_timeline(topic_name: str):
    """All conversations about a specific topic, date-ordered."""
    timeline = await neo4j.get_topic_timeline(topic_name)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Topic '{topic_name}' not found")
    return {"topic": topic_name, "conversations": timeline}
