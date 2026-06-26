"""Optional provider API keys set from the UI, held server-side.

The HYDRA-style "paste your key in the UI" convenience, without HYDRA's client-side
key exposure: a BYO-key field POSTs here, the key is written to a gitignored file
under the data dir and loaded into the process env so litellm (and
``llm.available_models``) pick it up. The browser never keeps the key — it submits
once and the field clears; reads only ever return *which* providers are configured,
never the values.

A key present in the real environment always WINS over a saved one (ops/CI > a
convenience file). See ~/.claude/rules/common/security.md — secrets stay out of git
and off the client.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import storage

# provider -> env var litellm reads. Mirrors llm.PROVIDERS deliberately WITHOUT
# importing llm (server imports both; this avoids an import cycle).
ENV_BY_PROVIDER: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama": "OLLAMA_BASE_URL",  # a base URL, not a secret, but same plumbing
}

KEYS_FILENAME = "provider_keys.json"


def _keys_file() -> Path:
    return Path(storage.DATA_DIR) / KEYS_FILENAME


def _read() -> dict[str, str]:
    f = _keys_file()
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_into_env() -> None:
    """Startup hook: apply saved keys to os.environ WITHOUT overriding a real env var."""
    for prov, val in _read().items():
        env = ENV_BY_PROVIDER.get(prov)
        if env and val and not os.environ.get(env):
            os.environ[env] = val


def set_key(provider: str, value: str) -> bool:
    """Persist (or clear, if value is empty) one provider key and apply it immediately.

    Returns False for an unknown provider. The empty-value case is how the UI clears
    a key. Writes are owner-only (0o600) on POSIX; best-effort on Windows.
    """
    env = ENV_BY_PROVIDER.get(provider)
    if not env:
        return False
    data = _read()
    value = (value or "").strip()
    if value:
        data[provider] = value
        os.environ[env] = value
    else:
        data.pop(provider, None)
        os.environ.pop(env, None)
    storage.ensure_data_dir()
    f = _keys_file()
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass
    return True


def configured() -> dict[str, bool]:
    """provider -> whether a key is currently present in env. NEVER returns values."""
    return {p: bool(os.environ.get(e)) for p, e in ENV_BY_PROVIDER.items()}
