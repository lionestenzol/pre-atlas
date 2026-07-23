"""Task B acceptance: the swappable-LLM proxy (litellm).

Proves:
  - GET /api/ai/models advertises ONLY providers whose key is present (no silent 401s)
  - POST /api/ai/complete is write-token guarded (it spends money)
  - a missing model is a 400, not a 500
  - a completion is normalized to the Anthropic shape the UI parses, for ANY provider
  - the back-compat /api/ai/anthropic alias routes through the same litellm path

litellm is mocked throughout, so these run with zero keys and zero network.
"""
from __future__ import annotations

import litellm
import pytest
from fastapi.testclient import TestClient

from droplist import auth
from droplist import server as S
from droplist.server import app


@pytest.fixture(autouse=True)
def _live_guard():
    """Force the real write-token guard (dependency_overrides is global)."""
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.pop(auth.require_write_token, None)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


client = TestClient(app)

_NO_KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "OLLAMA_BASE_URL"]


def test_models_filtered_by_present_keys(monkeypatch):
    for k in _NO_KEYS:
        monkeypatch.delenv(k, raising=False)
    r = client.get("/api/ai/models")
    assert r.status_code == 200
    assert r.json()["models"] == []  # no keys -> nothing offered

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    r = client.get("/api/ai/models")
    body = r.json()
    ids = [m["id"] for m in body["models"]]
    assert "openai/gpt-4o" in ids
    assert all(m["provider"] == "openai" for m in body["models"])  # anthropic stays hidden
    assert body["default"] == "openai/gpt-4o"


def test_complete_unauth_rejected():
    r = client.post("/api/ai/complete", json={"model": "openai/gpt-4o", "messages": []})
    assert r.status_code in (401, 403), r.text


def test_complete_missing_model_is_400():
    tok = auth.current_token()
    r = client.post("/api/ai/complete", json={"messages": []}, headers={"X-Atlas-Token": tok})
    assert r.status_code == 400, r.text


def _mock_litellm(monkeypatch, text="do the dishes"):
    class _Msg:
        content = text

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    monkeypatch.setattr(litellm, "completion", lambda **k: _Resp())
    monkeypatch.setattr(litellm, "completion_cost", lambda **k: 0.00042)


def test_complete_normalizes_to_anthropic_shape(monkeypatch):
    _mock_litellm(monkeypatch)
    tok = auth.current_token()
    r = client.post(
        "/api/ai/complete",
        json={"model": "openai/gpt-4o", "max_tokens": 50, "system": "s", "messages": [{"role": "user", "content": "x"}]},
        headers={"X-Atlas-Token": tok},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # UI parse is data.content[].text — must hold regardless of provider
    assert body["content"][0]["type"] == "text"
    assert body["content"][0]["text"] == "do the dishes"
    assert body["model"] == "openai/gpt-4o"
    assert body["estimated_cost"] == pytest.approx(0.00042, rel=1e-3)


def test_daily_budget_ceiling_returns_429(monkeypatch):
    # Task F: once today's spend crosses the ceiling, the route is refused BEFORE
    # it can spend more — the SaaS runaway-cost guard.
    monkeypatch.setattr(S, "DAILY_AI_BUDGET", 1.0)
    monkeypatch.setattr(S, "_today_ai_cost", lambda: 5.0)
    tok = auth.current_token()
    r = client.post(
        "/api/ai/complete",
        json={"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "x"}]},
        headers={"X-Atlas-Token": tok},
    )
    assert r.status_code == 429, r.text
    assert "budget" in r.text.lower()


def test_anthropic_alias_forces_provider_prefix(monkeypatch):
    captured = {}

    def fake_complete(model, messages, system=None, max_tokens=1024, purpose="complete"):
        captured["model"] = model
        return {"content": [{"type": "text", "text": "ok"}], "model": model, "estimated_cost": 0.0}

    monkeypatch.setattr(S.llm, "complete", fake_complete)
    tok = auth.current_token()
    r = client.post(
        "/api/ai/anthropic",
        json={"model": "claude-sonnet-4-20250514", "messages": [{"role": "user", "content": "x"}]},
        headers={"X-Atlas-Token": tok},
    )
    assert r.status_code == 200, r.text
    assert captured["model"] == "anthropic/claude-sonnet-4-20250514"
