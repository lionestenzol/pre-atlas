"""Run prediction engine and export results — runs as part of refresh.py pipeline.

Checks Neo4j availability. Writes stub prediction_results.json if Neo4j is down.
"""
import asyncio
import json
import socket
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE))

OUTPUT = BASE / "prediction_results.json"


def check_neo4j(host: str = "localhost", port: int = 7687, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def write_stub():
    """Write unavailable stub so downstream consumers don't crash."""
    stub = {
        "status": "unavailable",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_mode": None,
        "loop_predictions": [],
        "active_patterns": [],
        "mode_forecast": None,
        "exit_path": None,
        "top_actions": [],
        "graph_stats": {},
    }
    OUTPUT.write_text(json.dumps(stub, indent=2), encoding="utf-8")
    print("  [PREDICT] Wrote stub prediction_results.json (Neo4j unavailable)")


async def run_predictions():
    from mirofish.graph.neo4j_client import Neo4jClient
    from mirofish.prediction.insight_engine import InsightEngine

    neo4j = Neo4jClient()
    engine = InsightEngine(neo4j=neo4j)

    try:
        insights = await engine.get_daily_insights()
        result = asdict(insights)
        result["status"] = "ok"
        OUTPUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

        pred_count = len(result.get("loop_predictions", []))
        pattern_count = len(result.get("active_patterns", []))
        print(f"  [PREDICT] {pred_count} loop predictions, {pattern_count} patterns -> prediction_results.json")

    finally:
        await neo4j.close()


def main():
    if not check_neo4j():
        write_stub()
        return

    print("  [PREDICT] Running prediction engine...")
    asyncio.run(run_predictions())


if __name__ == "__main__":
    main()
