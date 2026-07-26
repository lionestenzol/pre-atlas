"""Tests for mirofish.graph.embedder."""
import pytest

from mirofish.graph.embedder import OllamaEmbedder


class TestEmbedder:
    @pytest.mark.asyncio
    async def test_embed_fails_gracefully_on_unreachable(self):
        """When Ollama is unreachable, embed raises after retries."""
        embedder = OllamaEmbedder(ollama_url="http://localhost:99999")
        with pytest.raises(Exception):
            await embedder.embed("test text")
        await embedder.close()

    @pytest.mark.asyncio
    async def test_embed_batch_calls_embed_per_text(self):
        """embed_batch processes each text sequentially."""
        call_count = 0
        embedder = OllamaEmbedder(ollama_url="http://localhost:99999")

        # Monkey-patch embed to return fake embeddings
        async def fake_embed(text):
            nonlocal call_count
            call_count += 1
            return [0.1, 0.2, 0.3]

        embedder.embed = fake_embed
        results = await embedder.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert call_count == 3
        assert results[0] == [0.1, 0.2, 0.3]
