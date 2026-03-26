"""Simulation runner — tick-based multi-agent swarm simulation via Ollama."""
import asyncio
import json
import random
import time
import uuid
import structlog
import httpx
from dataclasses import dataclass, field, asdict

from mirofish.config import config
from mirofish.swarm.personality import AgentProfile, PersonalityGenerator
from mirofish.swarm.store import SimulationStore
from mirofish.graph.neo4j_client import Neo4jClient

log = structlog.get_logger()


@dataclass
class AgentMessage:
    agent_id: str
    agent_name: str
    content: str
    reply_to: str | None = None
    sentiment: str = "neutral"  # positive, negative, neutral
    stance: str = "exploring"  # supporting, opposing, exploring, synthesizing


@dataclass
class SimulationConfig:
    topic: str
    agents: list[AgentProfile]
    tick_count: int = 10
    parallel_factor: int = 4
    document_context: str = ""


@dataclass
class SimulationResult:
    simulation_id: str
    topic: str
    agents: list[AgentProfile]
    ticks: list[list[AgentMessage]] = field(default_factory=list)
    duration_seconds: float = 0.0
    status: str = "pending"


AGENT_PROMPT = """You are participating in a discussion simulation about: {topic}

{personality}

{graph_context}

Previous messages in this discussion:
{history}

Generate your next contribution to this discussion. Be concise (2-4 sentences).
Respond in character based on your archetype and communication style.
If you disagree with someone, say so directly. If you agree, build on their point.

Your response (in character):"""


class SimulationRunner:
    """Run tick-based multi-agent simulations using Ollama."""

    def __init__(
        self,
        store: SimulationStore | None = None,
        neo4j: Neo4jClient | None = None,
        ollama_url: str | None = None,
        model: str | None = None,
    ):
        self.store = store or SimulationStore()
        self.neo4j = neo4j
        self.ollama_url = (ollama_url or config.ollama_url).rstrip("/")
        self.model = model or config.ollama_model
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(config.parallel_factor)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def run(self, sim_config: SimulationConfig, simulation_id: str | None = None) -> SimulationResult:
        """Run a full simulation.

        Args:
            sim_config: Simulation configuration.
            simulation_id: If provided, reuse an existing store record instead of creating a new one.

        Returns SimulationResult with all tick data.
        """
        agent_count = min(len(sim_config.agents), config.max_agents)
        tick_count = min(sim_config.tick_count, config.max_ticks)
        agents = sim_config.agents[:agent_count]

        if simulation_id is None:
            simulation_id = str(uuid.uuid4())
            # Create in store only if not pre-created by caller
            self.store.create_simulation(
                simulation_id=simulation_id,
                topic=sim_config.topic,
                agent_count=agent_count,
                tick_count=tick_count,
                agents=[a.to_dict() for a in agents],
            )

        result = SimulationResult(
            simulation_id=simulation_id,
            topic=sim_config.topic,
            agents=agents,
            status="running",
        )

        self.store.start_simulation(simulation_id)
        start_time = time.time()

        # Get graph context if Neo4j available
        graph_context = ""
        if self.neo4j and sim_config.document_context:
            try:
                nodes = await self.neo4j.search_similar([], limit=5)
                if nodes:
                    graph_context = "Related knowledge: " + "; ".join(
                        f"{n.name} ({n.type}): {n.description}" for n in nodes[:5]
                    )
            except Exception:
                pass

        # Run ticks
        all_messages: list[AgentMessage] = []

        for tick in range(tick_count):
            log.info("simulation.tick", simulation_id=simulation_id, tick=tick, total=tick_count)

            # Select active agents for this tick (not all agents post every tick)
            active_count = max(2, agent_count // 3)
            active_agents = random.sample(agents, min(active_count, len(agents)))

            # Generate messages in parallel with semaphore
            tick_messages = await self._run_tick(
                active_agents, sim_config.topic, graph_context, all_messages
            )

            all_messages.extend(tick_messages)
            result.ticks.append(tick_messages)

            # Persist tick
            self.store.save_tick(
                simulation_id,
                tick,
                [asdict(m) for m in tick_messages],
            )

        duration = time.time() - start_time
        result.duration_seconds = duration
        result.status = "completed"

        self.store.complete_simulation(simulation_id, duration)
        log.info(
            "simulation.completed",
            simulation_id=simulation_id,
            ticks=tick_count,
            messages=len(all_messages),
            duration=f"{duration:.1f}s",
        )

        return result

    async def _run_tick(
        self,
        agents: list[AgentProfile],
        topic: str,
        graph_context: str,
        history: list[AgentMessage],
    ) -> list[AgentMessage]:
        """Run one tick — each active agent generates a response."""
        tasks = [
            self._generate_agent_message(agent, topic, graph_context, history)
            for agent in agents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        messages = []
        for r in results:
            if isinstance(r, AgentMessage):
                messages.append(r)
            elif isinstance(r, Exception):
                log.warning("simulation.agent_error", error=str(r))
        return messages

    async def _generate_agent_message(
        self,
        agent: AgentProfile,
        topic: str,
        graph_context: str,
        history: list[AgentMessage],
    ) -> AgentMessage:
        """Generate a single agent's message for this tick."""
        async with self._semaphore:
            # Build history string (last 10 messages)
            recent = history[-10:]
            history_str = "\n".join(
                f"[{m.agent_name}]: {m.content}" for m in recent
            ) if recent else "(This is the start of the discussion)"

            prompt = AGENT_PROMPT.format(
                topic=topic,
                personality=agent.to_prompt_context(),
                graph_context=graph_context or "(No additional context)",
                history=history_str,
            )

            try:
                client = await self._get_client()
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
                resp.raise_for_status()
                content = resp.json().get("response", "").strip()

                return AgentMessage(
                    agent_id=agent.agent_id,
                    agent_name=agent.name,
                    content=content or "(No response)",
                    reply_to=recent[-1].agent_id if recent else None,
                )
            except Exception as e:
                return AgentMessage(
                    agent_id=agent.agent_id,
                    agent_name=agent.name,
                    content=f"(Agent unavailable: {str(e)[:50]})",
                )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self.store.close()
