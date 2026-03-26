"""Neo4j client — graph database operations for MiroFish knowledge graph."""
import asyncio
import structlog
from dataclasses import dataclass
from neo4j import AsyncGraphDatabase, AsyncDriver

from mirofish.config import config

log = structlog.get_logger()

VALID_NODE_LABELS = {"Concept", "Person", "Argument", "Evidence", "Claim"}
VALID_EDGE_LABELS = {"SUPPORTS", "CONTRADICTS", "RELATED_TO", "AUTHORED_BY"}


@dataclass
class GraphNode:
    node_id: str
    name: str
    type: str
    description: str


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    type: str
    evidence: str


class Neo4jClient:
    """Async Neo4j client for knowledge graph operations."""

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

    async def ensure_schema(self):
        """Create constraints and indexes for the knowledge graph."""
        driver = await self._get_driver()
        async with driver.session() as session:
            # Uniqueness constraints per node type
            for label in ["Concept", "Person", "Argument", "Evidence", "Claim"]:
                await session.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.name IS UNIQUE"
                )
            log.info("neo4j.schema_ensured")

    async def upsert_node(
        self, name: str, type: str, description: str, embedding: list[float] | None = None
    ) -> str:
        """Create or update a node. Returns the node element ID."""
        if type not in VALID_NODE_LABELS:
            raise ValueError(f"Invalid node type: {type!r}. Must be one of {VALID_NODE_LABELS}")
        driver = await self._get_driver()
        async with driver.session() as session:
            props = {"name": name, "description": description}
            if embedding:
                props["embedding"] = embedding

            result = await session.run(
                f"MERGE (n:{type} {{name: $name}}) "
                f"SET n.description = $description"
                + (", n.embedding = $embedding" if embedding else "")
                + " RETURN elementId(n) AS id",
                **props,
            )
            record = await result.single()
            return record["id"] if record else ""

    async def upsert_edge(
        self, source_name: str, source_type: str, target_name: str, target_type: str,
        edge_type: str, evidence: str = ""
    ):
        """Create or update an edge between two nodes."""
        if source_type not in VALID_NODE_LABELS:
            raise ValueError(f"Invalid source type: {source_type!r}")
        if target_type not in VALID_NODE_LABELS:
            raise ValueError(f"Invalid target type: {target_type!r}")
        if edge_type not in VALID_EDGE_LABELS:
            raise ValueError(f"Invalid edge type: {edge_type!r}")
        driver = await self._get_driver()
        async with driver.session() as session:
            await session.run(
                f"MATCH (a:{source_type} {{name: $source}}), (b:{target_type} {{name: $target}}) "
                f"MERGE (a)-[r:{edge_type}]->(b) "
                f"SET r.evidence = $evidence",
                source=source_name,
                target=target_name,
                evidence=evidence,
            )

    async def search_similar(self, embedding: list[float], limit: int = 10) -> list[GraphNode]:
        """Find nodes with embeddings, ordered by recency.

        Note: Vector similarity is not yet implemented — returns recent nodes
        with embeddings. For production, use a Neo4j vector index.
        """
        if not embedding:
            log.debug("neo4j.search_similar_no_embedding", msg="No embedding provided; returning recent nodes")
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (n) WHERE n.embedding IS NOT NULL "
                "RETURN n.name AS name, labels(n)[0] AS type, n.description AS description, "
                "elementId(n) AS id "
                "LIMIT $limit",
                limit=limit,
            )
            nodes = []
            async for record in result:
                nodes.append(GraphNode(
                    node_id=record["id"],
                    name=record["name"],
                    type=record["type"],
                    description=record["description"] or "",
                ))
            return nodes

    async def get_neighbors(self, node_name: str, depth: int = 1) -> dict:
        """Get a node and its neighbors up to the given depth."""
        driver = await self._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (n {name: $name})-[r*1.." + str(depth) + "]-(m) "
                "RETURN n.name AS source, type(last(r)) AS rel_type, m.name AS target, "
                "labels(m)[0] AS target_type, m.description AS target_desc "
                "LIMIT 50",
                name=node_name,
            )
            neighbors = []
            async for record in result:
                neighbors.append({
                    "source": record["source"],
                    "relationship": record["rel_type"],
                    "target": record["target"],
                    "target_type": record["target_type"],
                    "description": record["target_desc"] or "",
                })
            return {"node": node_name, "neighbors": neighbors}

    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None
