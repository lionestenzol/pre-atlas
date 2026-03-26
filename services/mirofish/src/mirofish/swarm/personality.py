"""Agent personality generator — creates diverse agent profiles for simulations."""
import json
import random
import asyncio
import structlog
import httpx
from dataclasses import dataclass, field, asdict

from mirofish.config import config

log = structlog.get_logger()

ARCHETYPES = [
    "Expert",
    "Devil's Advocate",
    "Synthesizer",
    "Pragmatist",
    "Visionary",
    "Skeptic",
    "Moderator",
]

COMMUNICATION_STYLES = [
    "academic",
    "casual",
    "provocative",
    "analytical",
    "skeptical",
]


@dataclass
class AgentProfile:
    """A simulated agent's personality and behavioral parameters."""
    agent_id: str
    name: str
    archetype: str
    knowledge_focus: list[str] = field(default_factory=list)
    traits: dict[str, float] = field(default_factory=dict)  # openness, agreeableness, assertiveness (0-1)
    communication_style: str = "analytical"
    goal: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_prompt_context(self) -> str:
        """Generate a prompt fragment describing this agent's personality."""
        return (
            f"You are {self.name}, a {self.archetype}. "
            f"Your communication style is {self.communication_style}. "
            f"You focus on: {', '.join(self.knowledge_focus)}. "
            f"Your goal: {self.goal}. "
            f"Traits — openness: {self.traits.get('openness', 0.5):.1f}, "
            f"agreeableness: {self.traits.get('agreeableness', 0.5):.1f}, "
            f"assertiveness: {self.traits.get('assertiveness', 0.5):.1f}."
        )


PERSONALITY_PROMPT = """Generate {count} unique agent personalities for a simulation about: {topic}

Each agent must have:
- name: A realistic name
- archetype: One of {archetypes}
- knowledge_focus: 2-3 areas of expertise relevant to the topic
- traits: openness (0-1), agreeableness (0-1), assertiveness (0-1)
- communication_style: One of {styles}
- goal: What this agent optimizes for in the discussion

Return ONLY valid JSON array of agent objects. Ensure archetype diversity (no more than 2 agents per archetype).
"""


class PersonalityGenerator:
    """Generate diverse agent personalities using Ollama."""

    def __init__(self, ollama_url: str | None = None, model: str | None = None):
        self.ollama_url = (ollama_url or config.ollama_url).rstrip("/")
        self.model = model or config.ollama_model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def generate(
        self, topic: str, count: int = 20, seed: int | None = None
    ) -> list[AgentProfile]:
        """Generate agent profiles for a simulation.

        Uses Ollama for creative generation, with fallback to deterministic
        generation if Ollama is unavailable.
        """
        if count > config.max_agents:
            count = config.max_agents

        rng = random.Random(seed)

        try:
            profiles = await self._generate_via_ollama(topic, count)
            if len(profiles) >= count:
                return profiles[:count]
        except Exception as e:
            log.warning("personality.ollama_failed", error=str(e))

        # Fallback: deterministic generation
        return self._generate_deterministic(topic, count, rng)

    async def _generate_via_ollama(self, topic: str, count: int) -> list[AgentProfile]:
        """Generate profiles using Ollama LLM."""
        prompt = PERSONALITY_PROMPT.format(
            count=count,
            topic=topic,
            archetypes=", ".join(ARCHETYPES),
            styles=", ".join(COMMUNICATION_STYLES),
        )

        client = await self._get_client()
        resp = await client.post(
            f"{self.ollama_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")

        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "agents" in data:
                data = data["agents"]
            if not isinstance(data, list):
                return []
        except json.JSONDecodeError:
            return []

        profiles = []
        for i, agent in enumerate(data):
            if not isinstance(agent, dict):
                continue
            profiles.append(AgentProfile(
                agent_id=f"agent_{i:03d}",
                name=agent.get("name", f"Agent {i}"),
                archetype=agent.get("archetype", ARCHETYPES[i % len(ARCHETYPES)]),
                knowledge_focus=agent.get("knowledge_focus", [topic]),
                traits=agent.get("traits", {"openness": 0.5, "agreeableness": 0.5, "assertiveness": 0.5}),
                communication_style=agent.get("communication_style", COMMUNICATION_STYLES[i % len(COMMUNICATION_STYLES)]),
                goal=agent.get("goal", f"Explore {topic}"),
            ))

        return profiles

    def _generate_deterministic(
        self, topic: str, count: int, rng: random.Random
    ) -> list[AgentProfile]:
        """Fallback: generate profiles deterministically without LLM."""
        profiles = []
        for i in range(count):
            archetype = ARCHETYPES[i % len(ARCHETYPES)]
            style = COMMUNICATION_STYLES[i % len(COMMUNICATION_STYLES)]
            profiles.append(AgentProfile(
                agent_id=f"agent_{i:03d}",
                name=f"{archetype} {i + 1}",
                archetype=archetype,
                knowledge_focus=[topic],
                traits={
                    "openness": round(rng.uniform(0.2, 0.9), 2),
                    "agreeableness": round(rng.uniform(0.2, 0.9), 2),
                    "assertiveness": round(rng.uniform(0.2, 0.9), 2),
                },
                communication_style=style,
                goal=f"Analyze {topic} from a {archetype.lower()} perspective",
            ))
        return profiles

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
