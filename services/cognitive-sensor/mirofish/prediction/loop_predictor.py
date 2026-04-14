"""Loop outcome predictor — KNN over conversation embeddings with behavioral corrections."""
import math
import structlog
from dataclasses import dataclass, field
from datetime import datetime

from mirofish.config import config
from mirofish.graph.neo4j_client import Neo4jClient

log = structlog.get_logger()

OUTCOMES = ["produced", "resolved", "looped", "abandoned"]


@dataclass
class LoopPrediction:
    convo_id: str
    title: str
    probabilities: dict[str, float]
    most_likely: str
    confidence: float
    evidence: list[str]
    similar_conversations: list[dict]


class LoopPredictor:
    """Predict outcomes for open loops using KNN + behavioral corrections."""

    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j

    async def predict(self, convo_id: str) -> LoopPrediction | None:
        """Predict the most likely outcome for an open loop."""
        # Get the conversation's embedding
        similar = await self.neo4j.find_similar_with_outcomes(convo_id, limit=config.prediction_k)
        if not similar:
            return None

        # Get the conversation's own properties
        rows = await self.neo4j._run(
            "MATCH (c:Conversation {convo_id: $cid}) "
            "RETURN c.title AS title, c.domain AS domain, c.emotional_trajectory AS trajectory, "
            "c.date AS date",
            cid=convo_id,
        )
        if not rows:
            return None
        record = rows[0]
        title = record.get("title") or f"Conversation {convo_id}"
        domain = record.get("domain") or "unknown"
        trajectory = record.get("trajectory") or "neutral"

        # Filter to only conversations with known outcomes (not open loops)
        neighbors = []
        for match in similar:
            props = match["properties"]
            outcome = props.get("outcome")
            if outcome and outcome in OUTCOMES and not props.get("is_open_loop"):
                neighbors.append({
                    "convo_id": props.get("convo_id"),
                    "title": props.get("title", ""),
                    "outcome": outcome,
                    "domain": props.get("domain", ""),
                    "trajectory": props.get("emotional_trajectory", ""),
                    "date": props.get("date", ""),
                    "similarity": match["score"],
                })

        if not neighbors:
            return LoopPrediction(
                convo_id=convo_id, title=title,
                probabilities={o: 0.25 for o in OUTCOMES},
                most_likely="looped", confidence=0.0,
                evidence=["No similar closed conversations found for comparison."],
                similar_conversations=[],
            )

        # Step 1: Weighted outcome tally
        scores = {o: 0.0 for o in OUTCOMES}
        total_weight = 0.0

        for n in neighbors:
            weight = n["similarity"]

            # Temporal decay: older conversations get less weight
            if n.get("date"):
                try:
                    days_ago = (datetime.now() - datetime.fromisoformat(n["date"])).days
                    decay = max(0.3, 1.0 - (days_ago / config.temporal_decay_days) * 0.7)
                    weight *= decay
                except (ValueError, TypeError):
                    pass

            # Domain boost: same-domain neighbors get 1.5x weight
            if n.get("domain") == domain:
                weight *= 1.5

            scores[n["outcome"]] += weight
            total_weight += weight

        # Step 2: Normalize to probabilities
        if total_weight > 0:
            probs = {o: s / total_weight for o, s in scores.items()}
        else:
            probs = {o: 0.25 for o in OUTCOMES}

        # Step 3: Behavioral corrections
        evidence = []

        # Check topic recurrence (abandoned pattern)
        topic_history = await self._check_topic_recurrence(convo_id)
        if topic_history["abandoned_count"] >= 2:
            probs["abandoned"] *= 1.3
            evidence.append(
                f"This topic appeared in {topic_history['total']} prior conversations, "
                f"{topic_history['abandoned_count']} were abandoned."
            )

        # Spiral trajectory correction
        if trajectory == "spiral":
            probs["abandoned"] *= 1.3
            probs["looped"] *= 1.2
            evidence.append("Emotional trajectory is 'spiral', which correlates with abandonment.")

        # Positive trajectory boost
        if trajectory == "positive_arc":
            probs["resolved"] *= 1.2
            probs["produced"] *= 1.2
            evidence.append("Positive emotional trajectory increases resolution probability.")

        # Renormalize
        total = sum(probs.values())
        if total > 0:
            probs = {o: p / total for o, p in probs.items()}

        # Compute confidence (1 - normalized entropy)
        confidence = _confidence_from_probs(probs)

        # Build evidence from neighbors
        most_likely = max(probs, key=probs.get)
        matching_neighbors = [n for n in neighbors if n["outcome"] == most_likely]
        if matching_neighbors:
            evidence.insert(0,
                f"{len(matching_neighbors)} of {len(neighbors)} similar conversations "
                f"had outcome '{most_likely}'."
            )

        # Domain evidence
        same_domain = [n for n in neighbors if n.get("domain") == domain]
        if same_domain:
            domain_outcomes = {}
            for n in same_domain:
                domain_outcomes[n["outcome"]] = domain_outcomes.get(n["outcome"], 0) + 1
            top_domain_outcome = max(domain_outcomes, key=domain_outcomes.get)
            evidence.append(
                f"In the '{domain}' domain, similar conversations most often "
                f"'{top_domain_outcome}' ({domain_outcomes[top_domain_outcome]}/{len(same_domain)})."
            )

        return LoopPrediction(
            convo_id=convo_id,
            title=title,
            probabilities={o: round(p, 3) for o, p in probs.items()},
            most_likely=most_likely,
            confidence=round(confidence, 3),
            evidence=evidence,
            similar_conversations=neighbors[:5],
        )

    async def predict_all_open(self) -> list[LoopPrediction]:
        """Predict outcomes for all open loops."""
        open_loops = await self.neo4j.get_open_loops()
        predictions = []
        for loop in open_loops:
            pred = await self.predict(loop["convo_id"])
            if pred:
                predictions.append(pred)
        return predictions

    async def _check_topic_recurrence(self, convo_id: str) -> dict:
        """Check if this conversation's topics have appeared before and their outcomes."""
        rows = await self.neo4j._run(
            "MATCH (c:Conversation {convo_id: $cid})-[:DISCUSSES]->(t:Topic)"
            "<-[:DISCUSSES]-(other:Conversation) "
            "WHERE other.convo_id <> $cid "
            "RETURN count(DISTINCT other) AS total, "
            "sum(CASE WHEN other.outcome = 'abandoned' THEN 1 ELSE 0 END) AS abandoned, "
            "sum(CASE WHEN other.outcome = 'looped' THEN 1 ELSE 0 END) AS looped",
            cid=convo_id,
        )
        if rows:
            record = rows[0]
            return {
                "total": record["total"],
                "abandoned_count": record["abandoned"],
                    "looped_count": record["looped"],
                }
            return {"total": 0, "abandoned_count": 0, "looped_count": 0}


def _confidence_from_probs(probs: dict[str, float]) -> float:
    """Confidence = 1 - normalized entropy. High agreement = high confidence."""
    n = len(probs)
    if n <= 1:
        return 1.0
    entropy = -sum(p * math.log2(p) if p > 0 else 0.0 for p in probs.values())
    max_entropy = math.log2(n)
    if max_entropy == 0:
        return 1.0
    return 1.0 - (entropy / max_entropy)
