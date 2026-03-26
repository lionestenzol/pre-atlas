"""Tests for mirofish.swarm.personality."""
import pytest
from unittest.mock import AsyncMock, patch

from mirofish.swarm.personality import (
    AgentProfile,
    ARCHETYPES,
    COMMUNICATION_STYLES,
    PersonalityGenerator,
)


class TestAgentProfile:
    def test_to_prompt_context(self):
        profile = AgentProfile(
            agent_id="agent_000",
            name="Dr. Smith",
            archetype="Expert",
            knowledge_focus=["AI", "testing"],
            traits={"openness": 0.8, "agreeableness": 0.6, "assertiveness": 0.7},
            communication_style="academic",
            goal="Provide deep analysis",
        )
        ctx = profile.to_prompt_context()
        assert "Dr. Smith" in ctx
        assert "Expert" in ctx
        assert "academic" in ctx
        assert "AI" in ctx
        assert "0.8" in ctx

    def test_to_dict_roundtrip(self):
        profile = AgentProfile(
            agent_id="agent_001",
            name="Jane",
            archetype="Skeptic",
            knowledge_focus=["economics"],
            traits={"openness": 0.5, "agreeableness": 0.5, "assertiveness": 0.5},
            communication_style="analytical",
            goal="Question assumptions",
        )
        d = profile.to_dict()
        assert d["agent_id"] == "agent_001"
        assert d["name"] == "Jane"
        assert d["archetype"] == "Skeptic"
        assert isinstance(d["traits"], dict)


class TestDeterministicGeneration:
    def test_correct_count(self):
        gen = PersonalityGenerator()
        import random
        profiles = gen._generate_deterministic("test topic", 10, random.Random(42))
        assert len(profiles) == 10

    def test_archetype_cycling(self):
        gen = PersonalityGenerator()
        import random
        profiles = gen._generate_deterministic("test", 14, random.Random(42))
        # First 7 should cycle through all archetypes
        first_seven = [p.archetype for p in profiles[:7]]
        assert set(first_seven) == set(ARCHETYPES)
        # 8th wraps to first archetype
        assert profiles[7].archetype == ARCHETYPES[0]

    def test_seed_reproducibility(self):
        gen = PersonalityGenerator()
        import random
        a = gen._generate_deterministic("topic", 5, random.Random(99))
        b = gen._generate_deterministic("topic", 5, random.Random(99))
        for pa, pb in zip(a, b):
            assert pa.traits == pb.traits
            assert pa.name == pb.name


class TestGenerateFallback:
    @pytest.mark.asyncio
    async def test_falls_back_on_ollama_failure(self):
        gen = PersonalityGenerator(ollama_url="http://localhost:99999")
        # Ollama unreachable → should fall back to deterministic
        profiles = await gen.generate("test topic", count=5, seed=42)
        assert len(profiles) == 5
        assert all(isinstance(p, AgentProfile) for p in profiles)
