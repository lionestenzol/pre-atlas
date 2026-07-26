"""Server-side BYO-key custody — the UI 'Add API key' field (HYDRA-style, but the
key never lives in the browser).

Proves:
  - POST /api/ai/keys is write-token guarded (it enables money-spending)
  - a saved key is applied to the env AND makes its provider appear in /api/ai/models
  - GET /api/ai/keys returns booleans only — the key value is never echoed
  - an empty key clears the provider
  - an unknown provider is a 400
  - a real environment variable is never clobbered by the saved file (ops > convenience)

Hermetic: data dir is a tmp path and provider env vars are cleared around each test.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from droplist import auth, keys
from droplist.server import app


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(keys.storage, "DATA_DIR", str(tmp_path))  # write the key file to tmp
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.pop(auth.require_write_token, None)  # force the real guard
    for env in keys.ENV_BY_PROVIDER.values():
        os.environ.pop(env, None)
    yield
    for env in keys.ENV_BY_PROVIDER.values():
        os.environ.pop(env, None)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


client = TestClient(app)


def _providers():
    return [m["provider"] for m in client.get("/api/ai/models").json()["models"]]


def test_set_key_unauth_rejected():
    r = client.post("/api/ai/keys", json={"provider": "openai", "key": "sk-x"})
    assert r.status_code in (401, 403), r.text


def test_set_key_applies_and_model_appears():
    tok = auth.current_token()
    assert "openai" not in _providers()
    r = client.post("/api/ai/keys", json={"provider": "openai", "key": "sk-test-123"}, headers={"X-Atlas-Token": tok})
    assert r.status_code == 200, r.text
    assert r.json()["configured"]["openai"] is True
    assert "sk-test-123" not in r.text  # the value is NEVER echoed back
    assert "openai/gpt-4o" in [m["id"] for m in r.json()["models"]]
    assert "openai" in _providers()  # picker would now offer it


def test_get_keys_is_booleans_only():
    tok = auth.current_token()
    client.post("/api/ai/keys", json={"provider": "anthropic", "key": "sk-ant-secret"}, headers={"X-Atlas-Token": tok})
    body = client.get("/api/ai/keys")
    assert body.json()["configured"]["anthropic"] is True
    assert "sk-ant-secret" not in body.text


def test_empty_key_clears_provider():
    tok = auth.current_token()
    client.post("/api/ai/keys", json={"provider": "openai", "key": "sk-test"}, headers={"X-Atlas-Token": tok})
    client.post("/api/ai/keys", json={"provider": "openai", "key": ""}, headers={"X-Atlas-Token": tok})
    assert client.get("/api/ai/keys").json()["configured"]["openai"] is False


def test_unknown_provider_is_400():
    tok = auth.current_token()
    r = client.post("/api/ai/keys", json={"provider": "nope", "key": "x"}, headers={"X-Atlas-Token": tok})
    assert r.status_code == 400, r.text


def test_real_env_var_wins_over_saved_file():
    keys.set_key("openai", "sk-saved")          # writes the file + applies to env
    os.environ["OPENAI_API_KEY"] = "sk-real-env"  # a real env var (CI/ops) takes precedence
    keys.load_into_env()                          # startup hook must NOT clobber it
    assert os.environ["OPENAI_API_KEY"] == "sk-real-env"
