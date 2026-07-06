"""Insight engine — orchestrates prediction modules into actionable daily output."""
import structlog
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from mirofish.graph.neo4j_client import Neo4jClient
from mirofish.prediction.loop_predictor import LoopPredictor, LoopPrediction
from mirofish.prediction.pattern_detector import PatternDetector, Pattern
from mirofish.prediction.mode_simulator import ModeSimulator

log = structlog.get_logger()


@dataclass
class TopAction:
    action: str
    impact: str
    effort: str
    evidence: str


@dataclass
class DailyInsights:
    generated_at: str
    current_mode: str
    current_risk: str
    build_allowed: bool
    loop_predictions: list[dict]
    active_patterns: list[dict]
    mode_forecast: dict
    exit_path: dict
    top_actions: list[dict]
    graph_stats: dict


class InsightEngine:
    """Orchestrate all prediction modules into a single coherent output."""

    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j
        self.loop_predictor = LoopPredictor(neo4j)
        self.pattern_detector = PatternDetector(neo4j)
        self.mode_simulator = ModeSimulator()

    async def get_daily_insights(self) -> DailyInsights:
        """Generate full daily prediction insights."""
        # 1. Predict outcomes for all open loops
        predictions = await self.loop_predictor.predict_all_open()

        # 2. Detect patterns
        patterns = await self.pattern_detector.detect_all()

        # 3. Get current mode and exit path
        exit_path = self.mode_simulator.find_exit_path()
        current_mode = exit_path.get("current_mode", "UNKNOWN")

        # Get current mode details
        from mirofish.prediction.mode_simulator import compute_mode
        state = self.mode_simulator._load_state()
        _, risk, build = compute_mode(
            state["closure_ratio"], state["open_loops"], state["closure_quality"]
        )

        # 4. Find easiest loops to close
        top_actions = self._rank_actions(predictions, patterns)

        # 5. Simulate closing the top actions
        if top_actions:
            sim_actions = [
                {"type": "close_loop", "target_id": a.get("convo_id", "")}
                for a in top_actions[:3]
            ]
            forecast = self.mode_simulator.simulate(sim_actions)
            forecast_dict = {
                "current_mode": forecast.current_mode,
                "projected_mode": forecast.projected_mode,
                "mode_changed": forecast.mode_changed,
                "transitions": forecast.transitions,
                "current_metrics": forecast.current_metrics,
                "projected_metrics": forecast.projected_metrics,
            }
        else:
            forecast_dict = {"message": "No open loops to simulate."}

        # 6. Graph stats
        stats = await self.neo4j.get_graph_stats()

        return DailyInsights(
            generated_at=datetime.now(timezone.utc).isoformat(),
            current_mode=current_mode,
            current_risk=risk,
            build_allowed=build,
            loop_predictions=[_prediction_to_dict(p) for p in predictions],
            active_patterns=[_pattern_to_dict(p) for p in patterns[:20]],
            mode_forecast=forecast_dict,
            exit_path=exit_path,
            top_actions=top_actions,
            graph_stats=stats,
        )

    def _rank_actions(self, predictions: list[LoopPrediction], patterns: list[Pattern]) -> list[dict]:
        """Rank open loops by how easy they are to close and impact."""
        actions = []

        for pred in predictions:
            # Score = P(resolved) + P(produced) — higher means easier to close
            resolve_prob = pred.probabilities.get("resolved", 0) + pred.probabilities.get("produced", 0)

            # Penalize spirals
            if any("spiral" in e.lower() for e in pred.evidence):
                resolve_prob *= 0.7

            actions.append({
                "convo_id": pred.convo_id,
                "title": pred.title,
                "action": f"Close '{pred.title}'",
                "resolve_probability": round(resolve_prob, 3),
                "most_likely_outcome": pred.most_likely,
                "confidence": pred.confidence,
                "impact": "Reduces open_loops by 1, improves closure metrics",
                "effort": _estimate_effort(pred),
                "evidence": pred.evidence[0] if pred.evidence else "",
            })

        # Sort: highest resolve probability first
        actions.sort(key=lambda a: a["resolve_probability"], reverse=True)
        return actions[:5]


def _estimate_effort(pred: LoopPrediction) -> str:
    """Estimate effort to close a loop based on signals."""
    signals = []
    if pred.probabilities.get("resolved", 0) > 0.4:
        signals.append("high resolution probability")
    if pred.probabilities.get("abandoned", 0) > 0.4:
        signals.append("high abandonment risk — may need triage decision")
    if pred.confidence > 0.7:
        signals.append("high confidence prediction")
    elif pred.confidence < 0.3:
        signals.append("low confidence — needs more data")

    if not signals:
        return "moderate effort"
    return "; ".join(signals)


def _prediction_to_dict(pred: LoopPrediction) -> dict:
    return {
        "convo_id": pred.convo_id,
        "title": pred.title,
        "probabilities": pred.probabilities,
        "most_likely": pred.most_likely,
        "confidence": pred.confidence,
        "evidence": pred.evidence,
        "similar_conversations": pred.similar_conversations[:3],
    }


def _pattern_to_dict(pattern: Pattern) -> dict:
    return {
        "pattern_id": pattern.pattern_id,
        "type": pattern.type,
        "description": pattern.description,
        "confidence": pattern.confidence,
        "evidence": pattern.evidence,
        "data": pattern.data,
    }
