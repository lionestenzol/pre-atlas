"""Neo4j client — HTTP-based knowledge graph for conversation analysis and prediction.

Uses Neo4j's HTTP transaction API instead of the bolt driver to avoid
driver compatibility issues on Windows.
"""
import structlog
import httpx
from dataclasses import dataclass
from base64 import b64encode

from mirofish.config import config

log = structlog.get_logger()

NODE_LABELS = {"Conversation", "Topic", "Idea", "Pattern", "ModeSnapshot"}
EDGE_LABELS = {
    "DISCUSSES", "SPAWNED_IDEA", "SIMILAR_TO",
    "PRECEDED_BY", "EXHIBITS", "RECURS_IN", "TRIGGERED_MODE",
}


@dataclass
class GraphNode:
    node_id: str
    label: str
    properties: dict


class Neo4jClient:
    """Neo4j client using HTTP transaction API."""

    def __init__(
        self,
        http_url: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        bolt_uri = config.neo4j_uri
        # Convert bolt://host:port to http://host:7474
        host = bolt_uri.replace("bolt://", "").split(":")[0]
        self.http_url = http_url or f"http://{host}:7474"
        self.user = user or config.neo4j_user
        self.password = password or config.neo4j_password
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            auth_bytes = b64encode(f"{self.user}:{self.password}".encode()).decode()
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Basic {auth_bytes}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def _run(self, cypher: str, **params: object) -> list[dict]:
        """Execute a Cypher query via HTTP and return rows as dicts."""
        client = await self._get_client()
        body = {
            "statements": [{
                "statement": cypher,
                "parameters": params,
                "resultDataContents": ["row"],
            }]
        }
        resp = await client.post(f"{self.http_url}/db/neo4j/tx/commit", json=body)
        resp.raise_for_status()
        data = resp.json()

        errors = data.get("errors", [])
        if errors:
            msg = errors[0].get("message", str(errors))
            log.warning("neo4j.query_error", error=msg, cypher=cypher[:80])
            return []

        results = data.get("results", [])
        if not results:
            return []

        columns = results[0].get("columns", [])
        rows = []
        for row_data in results[0].get("data", []):
            row_vals = row_data.get("row", [])
            rows.append(dict(zip(columns, row_vals)))
        return rows

    async def _exec(self, cypher: str, **params: object) -> None:
        """Execute a Cypher statement (no return data needed)."""
        await self._run(cypher, **params)

    async def ensure_schema(self) -> None:
        """Create constraints and indexes."""
        for label, prop in [
            ("Conversation", "convo_id"), ("Topic", "name"),
            ("Idea", "idea_id"), ("Pattern", "pattern_id"),
            ("ModeSnapshot", "date"),
        ]:
            await self._exec(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
            )

        for prop in ["domain", "outcome", "is_open_loop"]:
            await self._exec(f"CREATE INDEX IF NOT EXISTS FOR (c:Conversation) ON (c.{prop})")

        log.info("neo4j.schema_ensured")

    # ── Node operations ──────────────────────────────────────

    async def upsert_conversation(self, convo_id: str, properties: dict) -> None:
        # Neo4j HTTP API can't handle list[float] as embedding in SET +=
        # So we handle embedding separately
        embedding = properties.pop("embedding", None)
        await self._exec(
            "MERGE (c:Conversation {convo_id: $convo_id}) SET c += $props",
            convo_id=convo_id, props=properties,
        )
        if embedding:
            await self._exec(
                "MATCH (c:Conversation {convo_id: $convo_id}) SET c.embedding = $emb",
                convo_id=convo_id, emb=embedding,
            )

    async def upsert_topic(self, name: str, embedding: list[float] | None = None) -> None:
        if embedding:
            await self._exec(
                "MERGE (t:Topic {name: $name}) SET t.embedding = $emb",
                name=name, emb=embedding,
            )
        else:
            await self._exec("MERGE (t:Topic {name: $name})", name=name)

    async def upsert_idea(self, idea_id: str, properties: dict) -> None:
        await self._exec(
            "MERGE (i:Idea {idea_id: $idea_id}) SET i += $props",
            idea_id=idea_id, props=properties,
        )

    async def upsert_pattern(self, pattern_id: str, properties: dict) -> None:
        await self._exec(
            "MERGE (p:Pattern {pattern_id: $pattern_id}) SET p += $props",
            pattern_id=pattern_id, props=properties,
        )

    # ── Edge operations ──────────────────────────────────────

    async def link_conversation_topic(self, convo_id: str, topic_name: str, weight: float = 1.0) -> None:
        await self._exec(
            "MATCH (c:Conversation {convo_id: $cid}), (t:Topic {name: $tname}) "
            "MERGE (c)-[r:DISCUSSES]->(t) SET r.weight = $weight",
            cid=convo_id, tname=topic_name, weight=weight,
        )

    async def link_conversation_idea(self, convo_id: str, idea_id: str, confidence: float = 1.0) -> None:
        await self._exec(
            "MATCH (c:Conversation {convo_id: $cid}), (i:Idea {idea_id: $iid}) "
            "MERGE (c)-[r:SPAWNED_IDEA]->(i) SET r.confidence = $conf",
            cid=convo_id, iid=idea_id, conf=confidence,
        )

    async def link_similar(self, convo_id_a: str, convo_id_b: str,
                           similarity: float, shared_topics: list[str] | None = None) -> None:
        await self._exec(
            "MATCH (a:Conversation {convo_id: $a}), (b:Conversation {convo_id: $b}) "
            "MERGE (a)-[r:SIMILAR_TO]->(b) "
            "SET r.similarity = $sim, r.shared_topics = $topics",
            a=convo_id_a, b=convo_id_b, sim=similarity,
            topics=shared_topics or [],
        )

    async def link_temporal(self, convo_id_a: str, convo_id_b: str, days_gap: int) -> None:
        await self._exec(
            "MATCH (a:Conversation {convo_id: $a}), (b:Conversation {convo_id: $b}) "
            "MERGE (a)-[r:PRECEDED_BY]->(b) SET r.days_gap = $gap",
            a=convo_id_a, b=convo_id_b, gap=days_gap,
        )

    # ── Query operations ─────────────────────────────────────

    async def vector_search(self, embedding: list[float], label: str = "Conversation",
                            limit: int = 20, min_score: float = 0.5) -> list[dict]:
        """Brute-force vector search — fetch embeddings from Neo4j, compute cosine in Python."""
        rows = await self._run(
            f"MATCH (n:{label}) WHERE n.embedding IS NOT NULL "
            f"RETURN properties(n) AS props LIMIT 500"
        )
        results = []
        for row in rows:
            props = row.get("props", {})
            node_emb = props.get("embedding")
            if node_emb:
                score = _cosine_similarity(embedding, node_emb)
                if score >= min_score:
                    results.append({"properties": props, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    async def find_similar_with_outcomes(self, convo_id: str, limit: int = 20) -> list[dict]:
        rows = await self._run(
            "MATCH (c:Conversation {convo_id: $cid}) RETURN c.embedding AS emb",
            cid=convo_id,
        )
        if not rows or not rows[0].get("emb"):
            return []
        return await self.vector_search(rows[0]["emb"], "Conversation", limit, 0.3)

    async def find_recurring_topics(self, min_conversations: int = 5) -> list[dict]:
        return await self._run(
            "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
            "WITH t, count(c) AS conv_count, collect(c.outcome) AS outcomes, "
            "collect(c.date) AS dates "
            "WHERE conv_count >= $min "
            "RETURN t.name AS topic, conv_count, outcomes, dates "
            "ORDER BY conv_count DESC",
            min=min_conversations,
        )

    async def find_spiral_triggers(self, threshold: float = 0.6) -> list[dict]:
        return await self._run(
            "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
            "WITH t, count(c) AS total, "
            "sum(CASE WHEN c.outcome IN ['looped', 'abandoned'] OR "
            "c.emotional_trajectory = 'spiral' THEN 1 ELSE 0 END) AS bad "
            "WHERE total >= 3 AND toFloat(bad) / total >= $threshold "
            "RETURN t.name AS topic, total, bad, toFloat(bad)/total AS ratio "
            "ORDER BY ratio DESC",
            threshold=threshold,
        )

    async def find_closure_catalysts(self, threshold: float = 0.5) -> list[dict]:
        return await self._run(
            "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
            "WITH t, count(c) AS total, "
            "sum(CASE WHEN c.outcome IN ['produced', 'resolved'] THEN 1 ELSE 0 END) AS good "
            "WHERE total >= 3 AND toFloat(good) / total >= $threshold "
            "RETURN t.name AS topic, total, good, toFloat(good)/total AS ratio "
            "ORDER BY ratio DESC",
            threshold=threshold,
        )

    async def get_topic_timeline(self, topic_name: str) -> list[dict]:
        return await self._run(
            "MATCH (c:Conversation)-[r:DISCUSSES]->(t:Topic {name: $name}) "
            "RETURN c.convo_id AS convo_id, c.title AS title, c.date AS date, "
            "c.outcome AS outcome, c.emotional_trajectory AS trajectory, r.weight AS weight "
            "ORDER BY c.date",
            name=topic_name,
        )

    async def get_graph_stats(self) -> dict:
        stats = {}
        for label in NODE_LABELS:
            rows = await self._run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            stats[f"{label.lower()}_count"] = rows[0]["cnt"] if rows else 0

        edge_rows = await self._run(
            "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt"
        )
        stats["edges"] = {r["rel_type"]: r["cnt"] for r in edge_rows}

        top_rows = await self._run(
            "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
            "RETURN t.name AS topic, count(c) AS cnt "
            "ORDER BY cnt DESC LIMIT 20"
        )
        stats["top_topics"] = [{"topic": r["topic"], "count": r["cnt"]} for r in top_rows]
        return stats

    async def get_open_loops(self) -> list[dict]:
        return await self._run(
            "MATCH (c:Conversation {is_open_loop: true}) "
            "RETURN c.convo_id AS convo_id, c.title AS title, c.date AS date, "
            "c.domain AS domain, c.outcome AS outcome, c.loop_score AS loop_score, "
            "c.emotional_trajectory AS trajectory, c.intensity AS intensity "
            "ORDER BY c.loop_score DESC"
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
