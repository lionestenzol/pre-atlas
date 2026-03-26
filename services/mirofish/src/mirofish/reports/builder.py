"""Report builder — analyzes simulation data and generates structured reports."""
import json
import asyncio
import structlog
import httpx
from collections import Counter
from datetime import datetime, timezone

from mirofish.config import config
from mirofish.swarm.simulator import SimulationResult, AgentMessage

log = structlog.get_logger()

SUMMARY_PROMPT = """Analyze this multi-agent simulation discussion and produce a structured report.

Topic: {topic}
Agents: {agent_count}
Ticks: {tick_count}
Total messages: {message_count}

All messages:
{messages}

Generate a JSON report with:
{{
  "summary": "2-3 sentence executive summary of findings",
  "key_insights": ["insight 1", "insight 2", ...],
  "consensus_points": [{{"claim": "...", "confidence": 0.0-1.0, "supporting_agents": N}}],
  "dissent_points": [{{"claim": "...", "agents_for": N, "agents_against": N}}],
  "recommendations": [{{"action": "...", "priority": "high|medium|low", "rationale": "..."}}]
}}

Return ONLY valid JSON."""


class ReportBuilder:
    """Build structured reports from simulation results."""

    def __init__(self, ollama_url: str | None = None, model: str | None = None):
        self.ollama_url = (ollama_url or config.ollama_url).rstrip("/")
        self.model = model or config.ollama_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=180.0)
        return self._client

    async def build(self, result: SimulationResult) -> dict:
        """Build a report from simulation results.

        Returns a dict conforming to SimulationReport.v1.json schema.
        """
        # Flatten all messages
        all_messages: list[AgentMessage] = []
        for tick_messages in result.ticks:
            all_messages.extend(tick_messages)

        # Compute agent contributions
        agent_msg_counts = Counter(m.agent_id for m in all_messages)
        agent_contributions = []
        for agent in result.agents:
            count = agent_msg_counts.get(agent.agent_id, 0)
            influence = count / max(len(all_messages), 1)
            agent_contributions.append({
                "agent_id": agent.agent_id,
                "archetype": agent.archetype,
                "message_count": count,
                "influence_score": round(influence, 3),
            })

        # Try Ollama for analysis
        analysis = await self._analyze_via_ollama(result, all_messages)

        report = {
            "simulation_id": result.simulation_id,
            "schema_version": "1.0.0",
            "topic": result.topic,
            "agent_count": len(result.agents),
            "tick_count": len(result.ticks),
            "duration_seconds": round(result.duration_seconds, 2),
            "summary": analysis.get("summary", f"Simulation of '{result.topic}' with {len(result.agents)} agents over {len(result.ticks)} ticks."),
            "key_insights": analysis.get("key_insights", []),
            "consensus_points": analysis.get("consensus_points", []),
            "dissent_points": analysis.get("dissent_points", []),
            "recommendations": analysis.get("recommendations", []),
            "agent_contributions": agent_contributions,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return report

    async def _analyze_via_ollama(self, result: SimulationResult, messages: list[AgentMessage]) -> dict:
        """Use Ollama to analyze simulation messages and generate insights."""
        # Format messages for the prompt
        msg_text = "\n".join(
            f"[Tick {i // max(len(result.agents), 1)}] {m.agent_name} ({m.agent_id}): {m.content}"
            for i, m in enumerate(messages[:100])  # Cap at 100 messages for context
        )

        prompt = SUMMARY_PROMPT.format(
            topic=result.topic,
            agent_count=len(result.agents),
            tick_count=len(result.ticks),
            message_count=len(messages),
            messages=msg_text,
        )

        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            return json.loads(raw)
        except Exception as e:
            log.warning("report.ollama_failed", error=str(e))
            return {}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
