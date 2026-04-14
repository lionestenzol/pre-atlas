"""Conversation ingester — reads cognitive-sensor data into the Neo4j knowledge graph."""
import json
import structlog
from pathlib import Path

from mirofish.config import config
from mirofish.ingest_state import IngestState, load_state, save_state
from mirofish.graph.neo4j_client import Neo4jClient
from mirofish.graph.embedder import OllamaEmbedder
from mirofish.graph.conversation_chunker import chunk_conversation, get_user_text
from mirofish.graph.conversation_extractor import ConversationExtractor

log = structlog.get_logger()


class ConversationIngester:
    """Ingest real conversations from cognitive-sensor into Neo4j."""

    def __init__(
        self,
        neo4j: Neo4jClient | None = None,
        embedder: OllamaEmbedder | None = None,
        extractor: ConversationExtractor | None = None,
    ):
        self.neo4j = neo4j or Neo4jClient()
        self.embedder = embedder or OllamaEmbedder()
        self.extractor = extractor or ConversationExtractor()

    async def ingest_batch(self, batch_size: int | None = None, force: bool = False) -> dict:
        """Ingest a batch of conversations incrementally.

        Reads memory_db.json + conversation_classifications.json from cognitive-sensor.
        Skips already-ingested conversations using ingest_state.json.
        """
        batch_size = batch_size or config.ingest_batch_size
        state = load_state()

        # Load source data
        conversations = _load_json(config.memory_db_path)
        if not conversations:
            return {"error": "No conversations found", "path": str(config.memory_db_path)}

        classifications = _load_classifications()
        loops = _load_loops()

        # Ensure schema
        await self.neo4j.ensure_schema()

        # Determine range
        start_idx = 0 if force else (state.last_convo_index + 1)
        end_idx = min(start_idx + batch_size, len(conversations))

        if start_idx >= len(conversations):
            return {
                "status": "complete",
                "total_ingested": state.total_ingested,
                "total_conversations": len(conversations),
            }

        ingested = 0
        topics_created = set()

        for i in range(start_idx, end_idx):
            convo = conversations[i]
            convo_id = str(i)
            classification = classifications.get(convo_id, {})
            is_open_loop = convo_id in loops

            try:
                result = await self._ingest_one(convo, convo_id, classification, is_open_loop, loops.get(convo_id, 0))
                topics_created.update(result.get("topics", []))
                ingested += 1

                if ingested % 10 == 0:
                    log.info("ingest.progress", ingested=ingested, current=i, total=end_idx - start_idx)
            except Exception as e:
                log.error("ingest.conversation_failed", convo_id=convo_id, error=str(e))

        # Update state
        state.last_convo_index = end_idx - 1
        state.total_ingested += ingested
        state.topics_created += len(topics_created)
        save_state(state)

        return {
            "status": "batch_complete",
            "batch_ingested": ingested,
            "total_ingested": state.total_ingested,
            "total_conversations": len(conversations),
            "remaining": len(conversations) - end_idx,
            "new_topics": len(topics_created),
        }

    async def _ingest_one(self, convo: dict, convo_id: str, classification: dict,
                          is_open_loop: bool, loop_score: int) -> dict:
        """Ingest a single conversation into Neo4j."""
        messages = convo.get("messages", [])
        title = convo.get("title", f"Conversation {convo_id}")

        # Extract user text for embedding
        user_text = get_user_text(messages)
        if not user_text or len(user_text.split()) < 10:
            return {"topics": []}

        # Embed the conversation
        embedding = await self.embedder.embed(user_text[:2000])

        # Create Conversation node
        props = {
            "title": title,
            "date": classification.get("date", ""),
            "domain": classification.get("domain", "unknown"),
            "outcome": classification.get("outcome", "unknown"),
            "emotional_trajectory": classification.get("emotional_trajectory", "neutral"),
            "intensity": classification.get("intensity", "medium"),
            "word_count": classification.get("word_count", len(user_text.split())),
            "loop_score": loop_score,
            "is_open_loop": is_open_loop,
            "embedding": embedding,
        }
        await self.neo4j.upsert_conversation(convo_id, props)

        # Chunk and extract topics
        chunks = chunk_conversation(convo_id, messages)
        all_topics = set()

        for chunk in chunks[:3]:  # Cap at 3 chunks per conversation to limit Ollama calls
            extraction = await self.extractor.extract(chunk.text)
            for topic in extraction.get("topics", []):
                topic_name = topic["name"]
                all_topics.add(topic_name)
                await self.neo4j.upsert_topic(topic_name)
                await self.neo4j.link_conversation_topic(convo_id, topic_name, topic.get("salience", 0.5))

        return {"topics": list(all_topics)}

    async def build_similarity_edges(self, threshold: float | None = None) -> dict:
        """Post-ingestion: compute SIMILAR_TO edges via vector search."""
        threshold = threshold or config.similarity_threshold
        state = load_state()

        rows = await self.neo4j._run(
            "MATCH (c:Conversation) WHERE c.embedding IS NOT NULL "
            "RETURN c.convo_id AS cid, c.embedding AS emb"
        )
        conversations = [{"convo_id": r["cid"], "embedding": r["emb"]} for r in rows]

        edges_created = 0
        for i, convo in enumerate(conversations):
            similar = await self.neo4j.vector_search(convo["embedding"], "Conversation", limit=10, min_score=threshold)
            for match in similar:
                other_id = match["properties"].get("convo_id")
                if other_id and other_id != convo["convo_id"]:
                    await self.neo4j.link_similar(convo["convo_id"], other_id, match["score"])
                    edges_created += 1

            if (i + 1) % 50 == 0:
                log.info("similarity.progress", processed=i + 1, total=len(conversations))

        state.similarity_edges_built = True
        save_state(state)

        return {"edges_created": edges_created, "conversations_processed": len(conversations)}

    async def build_temporal_edges(self) -> dict:
        """Post-ingestion: link conversations on same topic by date."""
        topics = await self.neo4j.find_recurring_topics(min_conversations=2)
        edges_created = 0

        for topic_data in topics:
            timeline = await self.neo4j.get_topic_timeline(topic_data["topic"])
            for i in range(len(timeline) - 1):
                a = timeline[i]
                b = timeline[i + 1]
                if a.get("date") and b.get("date"):
                    try:
                        from datetime import datetime
                        da = datetime.fromisoformat(a["date"])
                        db = datetime.fromisoformat(b["date"])
                        gap = (db - da).days
                        await self.neo4j.link_temporal(a["convo_id"], b["convo_id"], gap)
                        edges_created += 1
                    except (ValueError, TypeError):
                        pass

        state = load_state()
        state.temporal_edges_built = True
        save_state(state)

        return {"edges_created": edges_created, "topics_processed": len(topics)}

    async def close(self) -> None:
        await self.neo4j.close()
        await self.embedder.close()
        await self.extractor.close()


def _load_json(path: Path) -> list | dict | None:
    """Load a JSON file, return None on failure."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.error("ingest.load_failed", path=str(path), error=str(e))
    return None


def _load_classifications() -> dict[str, dict]:
    """Load conversation classifications, indexed by convo_id."""
    data = _load_json(config.classifications_path)
    if not data:
        return {}
    if isinstance(data, dict) and "classifications" in data:
        data = data["classifications"]
    if not isinstance(data, list):
        return {}
    return {str(c.get("convo_id", "")): c for c in data if isinstance(c, dict)}


def _load_loops() -> dict[str, int]:
    """Load open loops as {convo_id: score}."""
    data = _load_json(config.loops_path)
    if not isinstance(data, list):
        return {}
    return {str(item.get("convo_id", "")): item.get("score", 0) for item in data}
