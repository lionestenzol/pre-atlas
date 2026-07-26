"""Pattern detector — finds recurring behavioral patterns via Neo4j graph queries."""
import structlog
from dataclasses import dataclass

from mirofish.config import config
from mirofish.graph.neo4j_client import Neo4jClient

log = structlog.get_logger()


@dataclass
class Pattern:
    pattern_id: str
    type: str  # recurring_topic, spiral_trigger, closure_catalyst, abandonment_sequence
    description: str
    confidence: float
    evidence: list[str]
    data: dict


class PatternDetector:
    """Detect recurring behavioral patterns across conversation history."""

    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j

    async def detect_all(self) -> list[Pattern]:
        """Run all pattern detectors and return combined results."""
        patterns = []
        patterns.extend(await self.detect_recurring_topics())
        patterns.extend(await self.detect_spiral_triggers())
        patterns.extend(await self.detect_closure_catalysts())
        patterns.extend(await self.detect_abandonment_sequences())
        patterns.extend(await self.detect_domain_patterns())
        return patterns

    async def detect_recurring_topics(self) -> list[Pattern]:
        """Topics that keep coming back in 5+ conversations."""
        topics = await self.neo4j.find_recurring_topics(config.min_pattern_frequency)
        patterns = []
        for t in topics:
            outcomes = t["outcomes"]
            total = t["conversation_count"]
            looped = sum(1 for o in outcomes if o in ("looped", "abandoned"))
            produced = sum(1 for o in outcomes if o in ("produced", "resolved"))

            description = f"'{t['topic']}' appears in {total} conversations"
            evidence = []

            if looped > produced:
                description += f" — mostly unresolved ({looped}/{total} looped/abandoned)"
                evidence.append(f"{looped} of {total} conversations on this topic didn't produce results.")
            else:
                description += f" — mostly productive ({produced}/{total} produced/resolved)"
                evidence.append(f"{produced} of {total} conversations on this topic produced results.")

            patterns.append(Pattern(
                pattern_id=f"recurring_{t['topic'][:30]}",
                type="recurring_topic",
                description=description,
                confidence=min(1.0, total / 10),  # More data = more confident
                evidence=evidence,
                data={"topic": t["topic"], "count": total, "looped": looped, "produced": produced},
            ))
        return patterns

    async def detect_spiral_triggers(self) -> list[Pattern]:
        """Topics where conversations reliably go negative."""
        triggers = await self.neo4j.find_spiral_triggers(threshold=0.6)
        patterns = []
        for t in triggers:
            patterns.append(Pattern(
                pattern_id=f"spiral_{t['topic'][:30]}",
                type="spiral_trigger",
                description=(
                    f"'{t['topic']}' triggers negative outcomes "
                    f"{t['negative_count']}/{t['total_conversations']} times "
                    f"({t['negative_ratio']:.0%})"
                ),
                confidence=t["negative_ratio"],
                evidence=[
                    f"{t['negative_count']} of {t['total_conversations']} conversations "
                    f"on this topic resulted in looping, abandonment, or spiral.",
                ],
                data=t,
            ))
        return patterns

    async def detect_closure_catalysts(self) -> list[Pattern]:
        """Topics/domains where things actually get done."""
        catalysts = await self.neo4j.find_closure_catalysts(threshold=0.5)
        patterns = []
        for t in catalysts:
            patterns.append(Pattern(
                pattern_id=f"catalyst_{t['topic'][:30]}",
                type="closure_catalyst",
                description=(
                    f"'{t['topic']}' leads to productive outcomes "
                    f"{t['positive_count']}/{t['total_conversations']} times "
                    f"({t['positive_ratio']:.0%})"
                ),
                confidence=t["positive_ratio"],
                evidence=[
                    f"{t['positive_count']} of {t['total_conversations']} conversations "
                    f"on this topic produced results or resolved.",
                ],
                data=t,
            ))
        return patterns

    async def detect_abandonment_sequences(self) -> list[Pattern]:
        """Topics where 3+ consecutive conversations were all abandoned."""
        driver = await self.neo4j._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Conversation)-[:DISCUSSES]->(t:Topic) "
                "WITH t, c ORDER BY c.date "
                "WITH t, collect({id: c.convo_id, outcome: c.outcome, title: c.title, date: c.date}) AS convos "
                "WHERE size(convos) >= 3 "
                "RETURN t.name AS topic, convos"
            )
            patterns = []
            async for record in result:
                topic = record["topic"]
                convos = list(record["convos"])
                # Find runs of 3+ abandoned
                run = []
                for c in convos:
                    if c["outcome"] in ("abandoned", "looped"):
                        run.append(c)
                    else:
                        if len(run) >= 3:
                            patterns.append(Pattern(
                                pattern_id=f"abandon_seq_{topic[:20]}_{len(patterns)}",
                                type="abandonment_sequence",
                                description=(
                                    f"'{topic}': {len(run)} consecutive conversations abandoned/looped"
                                ),
                                confidence=min(1.0, len(run) / 5),
                                evidence=[
                                    f"Conversations: {', '.join(c.get('title', '?')[:30] for c in run[:3])}..."
                                ],
                                data={"topic": topic, "run_length": len(run),
                                      "convo_ids": [c["id"] for c in run]},
                            ))
                        run = []
                # Check final run
                if len(run) >= 3:
                    patterns.append(Pattern(
                        pattern_id=f"abandon_seq_{topic[:20]}_{len(patterns)}",
                        type="abandonment_sequence",
                        description=f"'{topic}': {len(run)} consecutive conversations abandoned/looped",
                        confidence=min(1.0, len(run) / 5),
                        evidence=[f"Conversations: {', '.join(c.get('title', '?')[:30] for c in run[:3])}..."],
                        data={"topic": topic, "run_length": len(run),
                              "convo_ids": [c["id"] for c in run]},
                    ))
            return patterns

    async def detect_domain_patterns(self) -> list[Pattern]:
        """Which domains produce results vs which don't."""
        driver = await self.neo4j._get_driver()
        async with driver.session() as session:
            result = await session.run(
                "MATCH (c:Conversation) WHERE c.domain IS NOT NULL "
                "WITH c.domain AS domain, count(c) AS total, "
                "sum(CASE WHEN c.outcome IN ['produced', 'resolved'] THEN 1 ELSE 0 END) AS good, "
                "sum(CASE WHEN c.outcome IN ['looped', 'abandoned'] THEN 1 ELSE 0 END) AS bad "
                "WHERE total >= 5 "
                "RETURN domain, total, good, bad, toFloat(good)/total AS success_rate "
                "ORDER BY success_rate DESC"
            )
            patterns = []
            async for record in result:
                domain = record["domain"]
                rate = record["success_rate"]
                total = record["total"]
                patterns.append(Pattern(
                    pattern_id=f"domain_{domain}",
                    type="closure_catalyst" if rate >= 0.4 else "spiral_trigger",
                    description=(
                        f"Domain '{domain}': {rate:.0%} success rate "
                        f"({record['good']}/{total} productive, {record['bad']}/{total} unproductive)"
                    ),
                    confidence=min(1.0, total / 20),
                    evidence=[
                        f"Across {total} conversations in '{domain}', "
                        f"{record['good']} produced/resolved and {record['bad']} looped/abandoned."
                    ],
                    data={"domain": domain, "total": total, "good": record["good"],
                          "bad": record["bad"], "success_rate": rate},
                ))
            return patterns
