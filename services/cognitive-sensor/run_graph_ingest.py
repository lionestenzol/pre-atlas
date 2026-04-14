"""Incremental Neo4j graph ingestion — runs as part of refresh.py pipeline.

Checks Neo4j and Ollama availability before running. Gracefully skips if either is down.
"""
import asyncio
import json
import socket
import sys
from pathlib import Path

BASE = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE))

from mirofish.ingest_state import load_state


def check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    """Check if a TCP port is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_ollama(url: str = "http://localhost:11434", timeout: float = 3.0) -> bool:
    """Check if Ollama HTTP API is reachable."""
    import urllib.request
    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


async def run_ingestion():
    from mirofish.graph.neo4j_client import Neo4jClient
    from mirofish.graph.ingester import ConversationIngester
    from mirofish.ingest_state import load_state as _load

    neo4j = Neo4jClient()
    ingester = ConversationIngester(neo4j=neo4j)

    try:
        result = await ingester.ingest_batch(batch_size=50)
        print(f"  [INGEST] {json.dumps(result)}")

        # Build edges if not yet done
        state = _load()
        if state.total_ingested > 0 and not state.similarity_edges_built:
            print("  [INGEST] Building similarity edges...")
            edge_result = await ingester.build_similarity_edges()
            print(f"  [INGEST] Similarity edges: {edge_result}")

        if state.total_ingested > 0 and not state.temporal_edges_built:
            print("  [INGEST] Building temporal edges...")
            temporal_result = await ingester.build_temporal_edges()
            print(f"  [INGEST] Temporal edges: {temporal_result}")

    finally:
        await ingester.close()


def main():
    # Check Neo4j
    if not check_tcp("localhost", 7687):
        print("  [SKIP] run_graph_ingest.py — Neo4j not available on port 7687")
        return

    # Check Ollama
    if not check_ollama():
        print("  [SKIP] run_graph_ingest.py — Ollama not available on port 11434")
        return

    state = load_state()
    print(f"  [INGEST] Starting ingestion (previously ingested: {state.total_ingested})")
    asyncio.run(run_ingestion())


if __name__ == "__main__":
    main()
