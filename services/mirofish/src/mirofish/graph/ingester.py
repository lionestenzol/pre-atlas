"""Document ingestion pipeline — chunks, embeds, extracts entities, writes to Neo4j."""
import structlog

from mirofish.graph.chunker import chunk_document
from mirofish.graph.embedder import OllamaEmbedder
from mirofish.graph.extractor import EntityExtractor
from mirofish.graph.neo4j_client import Neo4jClient

log = structlog.get_logger()


class DocumentIngester:
    """Full ingestion pipeline: document → chunks → embeddings → entities → Neo4j."""

    def __init__(
        self,
        neo4j: Neo4jClient | None = None,
        embedder: OllamaEmbedder | None = None,
        extractor: EntityExtractor | None = None,
    ):
        self.neo4j = neo4j or Neo4jClient()
        self.embedder = embedder or OllamaEmbedder()
        self.extractor = extractor or EntityExtractor()

    async def ingest_document(self, text: str, chunk_size: int = 500) -> dict:
        """Ingest a document into the knowledge graph.

        Pipeline: chunk → embed → extract entities → write to Neo4j.

        Returns summary dict with counts.
        """
        # Ensure Neo4j schema
        await self.neo4j.ensure_schema()

        # Chunk the document
        chunks = chunk_document(text, chunk_size=chunk_size)
        log.info("ingester.chunked", count=len(chunks))

        total_entities = 0
        total_relationships = 0

        for chunk in chunks:
            # Embed the chunk
            embedding = await self.embedder.embed(chunk.text)

            # Extract entities and relationships
            extraction = await self.extractor.extract(chunk.text)
            log.info(
                "ingester.extracted",
                chunk=chunk.index,
                entities=len(extraction.entities),
                relationships=len(extraction.relationships),
            )

            # Write entities to Neo4j
            for entity in extraction.entities:
                await self.neo4j.upsert_node(
                    name=entity.name,
                    type=entity.type,
                    description=entity.description,
                    embedding=embedding,
                )
                total_entities += 1

            # Write relationships to Neo4j
            for rel in extraction.relationships:
                # Find entity types for source and target
                source_type = "Concept"
                target_type = "Concept"
                for e in extraction.entities:
                    if e.name == rel.source:
                        source_type = e.type
                    if e.name == rel.target:
                        target_type = e.type

                await self.neo4j.upsert_edge(
                    source_name=rel.source,
                    source_type=source_type,
                    target_name=rel.target,
                    target_type=target_type,
                    edge_type=rel.type,
                    evidence=rel.evidence,
                )
                total_relationships += 1

        return {
            "chunks": len(chunks),
            "entities": total_entities,
            "relationships": total_relationships,
        }

    async def close(self):
        await self.neo4j.close()
        await self.embedder.close()
        await self.extractor.close()
