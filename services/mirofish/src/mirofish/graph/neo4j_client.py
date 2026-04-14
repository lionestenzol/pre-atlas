"""Neo4j client — knowledge graph for conversation analysis and prediction."""
import structlog
from dataclasses import dataclass
from neo4j import AsyncGraphDatabase, AsyncDriver

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
    """Async Neo4j client for the conversation knowledge graph."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.uri = uri or config.neo4j_uri
        self.user = user or config.neo4j_user
        self.password = password or config.neo4j_password
        self._driver: AsyncDriver | None = None

    async def _get_driver(self) -> AsyncDriver:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self._driver

    async def ensure_schema(self) -> None:
        """Create constraints, indexes, and vector indexes."""
        driver = await self._get_driver()
        async with driver.session() as session:
            # Uniqueness constraints
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Conversation) REQUIRE c.convo_id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Idea) REQUIRE i.idea_id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Pattern) REQUIRE p.pattern_id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (m:ModeSnapshot) REQUIRE m.date IS UNIQUE"
            )

            # Regular indexes for frequent lookups
            await session.run(
                "CREATE INDEX IF NOT EXISTS FOR (c:Conversation) ON (c.domain)"
            )
            await session.run(
                "CREATE INDEX IF NOT EXISTS FOR (c:Conversation) ON (c.outcome)"
            )
            await session.run(
                "CREATE INDEX IF NOT EXISTS FOR (c:Conversation) ON (c.is_open_loop)"
            )

            # Vector indexes for similarity search (Neo4j 5.x)
            try:
                await session.run(
                    "CREATE VECTOR INDEX conversation_embeddings IF NOT EXISTS "
                    "FOR (c:Conversation) ON c.embedding "
                    "OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}"
                )
                await session.run(
                    "CREATE VECTOR INDEX topic_embeddings IF NOT EXISTS "
                    "FOR (t:Topic) ON t.embedding "
                    "OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}"
                )
                log.info("neo4j.vector_indexes_created")
            except Exception as e:
                log.warning("neo4j.vector_index_failed", error=str(e),
                            msg="Vector indexes require Neo4j 5.11+. Falling back to brute force.")

        log.info("neo4j.schema_ensured")

    # ── Node operations ──────────────────────────────────────

    async def upsert_conversation(self, convo_id: str, properties: dict) -> None:
        """Create or update a Conversation node."""
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                "MERGE (c:Conversation {convo_id: $convo_id}) "
                "SET c += $props",
                convo_id=convo_id, props=properties,
            )

    async def upsert_topic(self, name: str, embedding: list[float] | None = None) -> None:
        """Create or update a Topic node."""
        driver = await self._get_driver()
        async with driver.session() as session:
            if embedding:
                await session.run(
                    "MERGE (t:Topic {name: $name}) SET t.embedding = $embedding",
                    name=name, embedding=embedding,
                )
            else:
                await session.run(
                    "MERGE (t:Topic {name: $name})", name=name,
                )

    async def upsert_idea(self, idea_id: str, properties: dict) -> None:
        """Create or update an Idea node."""
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                "MERGE (i:Idea {idea_id: $idea_id}) SET i += $props",
                idea_id=idea_id, props=properties,
            )

    async def upsert_pattern(self, pattern_id: str, properties: dict) -> None:
        """Create or update a Pattern node."""
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                "MERGE (p:Pattern {pattern_id: $pattern_id}) SET p += $props",
                pattern_id=pattern_id, props=properties,
            )

    # ── Edge operations ──────────────────────────────────────

    async def link_conversation_topic(self, convo_id: str, topic_name: str, weight: float = 1.0) -> None:
        """Create DISCUSSES edge between Conversation and Topic."""
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                "MATCH (c:Conversation {convo_id: $cid}), (t:Topic {name: $tname}) "
                "MERGE (c)-[r:DISCUSSES]->(t) SET r.weight = $weight",
                cid=convo_id, tname=topic_name, weight=weight,
            )

    async def link_conversation_idea(self, convo_id: str, idea_id: str, confidence: float = 1.0) -> None:
        """Create SPAWNED_IDEA edge."""
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                "MATCH (c:Conversation {convo_id: $cid}), (i:Idea {idea_id: $iid}) "
                "MERGE (c)-[r:SPAWNED_IDEA]->(i) SET r.confidence = $conf",
                cid=convo_id, iid=idea_id, conf=confidence,
            )

    async def link_similar(self, convo_id_a: str, convo_id_b: str,
                           similarity: float, shared_topics: list[str] | None = None) -> None:
        """Create SIMILAR_TO edge between two conversations."""
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                "MATCH (a:Conversation {convo_id: $a}), (b:Conversation {convo_id: $b}) "
                "MERGE (a)-[r:SIMILAR_TO]->(b) "
                "SET r.similarity = $sim, r.shared_topics = $topics",
                a=convo_id_a, b=convo_id_b, sim=similarity,
                topics=shared_topics or [],
            )

    async def link_temporal(self, convo_id_a: str, convo_id_b: str, days_gap: int) -> None:
        """Create PRECEDED_BY edge (a preceded b on same topic)."""
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                "MATCH (a:Conversation {convo_id: $a}), (b:Conversation {convo_id: $b}) "
                "MERGE (a)-[r:PRECEDED_BY]->(b) SET r.days_gap = $gap",
                a=convo_id_a, b=convo_id_b, gap=days_gap,
            )

    # ── Query operations ─────────────────────────────────────

    async def vector_search(self, embedding: list[float], label: str = "Conversation",
                            limit: int = 20, min_score: float = 0.5) -> list[dict]:
        """Vector similarity search using Neo4j vector index."""
        index_name = f"{label.lower()}_embeddings"
        driver = await self._get_driver()
        async with driver.session() as session:
            try:
                result = await session.run(
                    f"CALL db.index.vector.queryNodes('{index_name}', $limit, $embedding) "
                    f"YIELD node, score WHERE score >= $min_score "
                    f"RETURN node, score ORDER BY score DESC",
                    limit=limit, embedding=embedding, min_score=min_score,
                )
                rows = []
                async for record in result:
                    node = record["node"]
                    rows.append({"properties": dict(node), "score": record["score"]})
                return rows
            except Exception as e:
                log.warning("neo4j.vector_search_fallback", error=str(e))
                return await self._brute_force_search(embedding, label, limit, min_score)

    async def _brute_force_search(self, embedding: list[float], label: str,
                                   limit: int, min_score: float) -> list[dict]:
        """Fallback: fetch all nodes with embeddings and compute cosine in Python."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                f"MATCH (n:{label}) WHERE n.embedding IS NOT NULL "
                f"RETURN n LIMIT 500"
            )
            nodes = []
            async for record in result:
                node = dict(record["n"])
                node_emb = node.get("embedding")
                if node_emb:
                    score = _cosine_similarity(embedding, node_emb)
                    if score >= min_score:
                        nodes.append({"properties": node, "score": score})
            nodes.sort(key=lambda x: x["score"], reverse=True)
            return nodes[:limit]

    async def find_similar_with_outcomes(self, convo_id: str, limit: int = 20) -> list[dict]:
        """Find conversations similar to the given one, returning their outcomes."""
        driver = await self._get_driver()
        async with driver.session() as session:
            # First get the conversation's embedding
            result = await session.run(
                "MATCH (c:Conversation {convo_id: $cid}) RETURN c.embedding AS emb",
                cid=convo_id,
            )
            record = await result.single()
            if not record or not record["emb"]:
                return []
            return await self.vector_search(record["emb"], "Conversation", limit, 0.3)

    async def find_recurring_topics(self, min_conversations: int = 5) -> list[dict]:
        """Topics appearing in N+ conversations."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
                "WITH t, count(c) AS conv_count, collect(c.outcome) AS outcomes, "
                "collect(c.date) AS dates "
                "WHERE conv_count >= $min "
                "RETURN t.name AS topic, conv_count, outcomes, dates "
                "ORDER BY conv_count DESC",
                min=min_conversations,
            )
            rows = []
            async for record in result:
                rows.append({
                    "topic": record["topic"],
                    "conversation_count": record["conv_count"],
                    "outcomes": list(record["outcomes"]),
                    "dates": list(record["dates"]),
                })
            return rows

    async def find_spiral_triggers(self, threshold: float = 0.6) -> list[dict]:
        """Topics where >threshold of conversations loop or spiral."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
                "WITH t, count(c) AS total, "
                "sum(CASE WHEN c.outcome IN ['looped', 'abandoned'] OR "
                "c.emotional_trajectory = 'spiral' THEN 1 ELSE 0 END) AS bad "
                "WHERE total >= 3 AND toFloat(bad) / total >= $threshold "
                "RETURN t.name AS topic, total, bad, toFloat(bad)/total AS ratio "
                "ORDER BY ratio DESC",
                threshold=threshold,
            )
            rows = []
            async for record in result:
                rows.append({
                    "topic": record["topic"],
                    "total_conversations": record["total"],
                    "negative_count": record["bad"],
                    "negative_ratio": record["ratio"],
                })
            return rows

    async def find_closure_catalysts(self, threshold: float = 0.5) -> list[dict]:
        """Topics/domains where >threshold of conversations produce or resolve."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
                "WITH t, count(c) AS total, "
                "sum(CASE WHEN c.outcome IN ['produced', 'resolved'] THEN 1 ELSE 0 END) AS good "
                "WHERE total >= 3 AND toFloat(good) / total >= $threshold "
                "RETURN t.name AS topic, total, good, toFloat(good)/total AS ratio "
                "ORDER BY ratio DESC",
                threshold=threshold,
            )
            rows = []
            async for record in result:
                rows.append({
                    "topic": record["topic"],
                    "total_conversations": record["total"],
                    "positive_count": record["good"],
                    "positive_ratio": record["ratio"],
                })
            return rows

    async def get_topic_timeline(self, topic_name: str) -> list[dict]:
        """All conversations about a topic, date-ordered."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Conversation)-[r:DISCUSSES]->(t:Topic {name: $name}) "
                "RETURN c.convo_id AS convo_id, c.title AS title, c.date AS date, "
                "c.outcome AS outcome, c.emotional_trajectory AS trajectory, r.weight AS weight "
                "ORDER BY c.date",
                name=topic_name,
            )
            rows = []
            async for record in result:
                rows.append(dict(record))
            return rows

    async def get_graph_stats(self) -> dict:
        """Node counts, edge counts, top topics by degree."""
        driver = await self._get_driver()
        async with driver.session() as session:
            stats = {}
            for label in NODE_LABELS:
                result = await session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
                record = await result.single()
                stats[f"{label.lower()}_count"] = record["cnt"] if record else 0

            # Edge counts
            result = await session.run(
                "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt"
            )
            edge_counts = {}
            async for record in result:
                edge_counts[record["rel_type"]] = record["cnt"]
            stats["edges"] = edge_counts

            # Top topics
            result = await session.run(
                "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
                "RETURN t.name AS topic, count(c) AS cnt "
                "ORDER BY cnt DESC LIMIT 20"
            )
            top_topics = []
            async for record in result:
                top_topics.append({"topic": record["topic"], "count": record["cnt"]})
            stats["top_topics"] = top_topics

            return stats

    async def get_open_loops(self) -> list[dict]:
        """Get all conversations marked as open loops."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Conversation {is_open_loop: true}) "
                "RETURN c.convo_id AS convo_id, c.title AS title, c.date AS date, "
                "c.domain AS domain, c.outcome AS outcome, c.loop_score AS loop_score, "
                "c.emotional_trajectory AS trajectory, c.intensity AS intensity "
                "ORDER BY c.loop_score DESC"
            )
            rows = []
            async for record in result:
                rows.append(dict(record))
            return rows

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
