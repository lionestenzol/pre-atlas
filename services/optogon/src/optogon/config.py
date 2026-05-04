"""Optogon configuration. Resolved at import time; no dynamic reload."""
from __future__ import annotations
import os
from pathlib import Path


# Repo root: services/optogon/src/optogon/config.py -> parents[4] = repo root
REPO_ROOT = Path(__file__).resolve().parents[4]

SERVICE_DIR = REPO_ROOT / "services" / "optogon"
PATHS_DIR = SERVICE_DIR / "paths"
DATA_DIR = SERVICE_DIR / "data"
DB_PATH = DATA_DIR / "sessions.db"

CONTRACTS_DIR = REPO_ROOT / "contracts"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"

# Server
HOST = os.environ.get("OPTOGON_HOST", "0.0.0.0")
PORT = int(os.environ.get("OPTOGON_PORT", "3010"))

# Signal transport · Ship Target #1
# OPTOGON_SIGNAL_EMIT three-switch ladder (matches cortex_bridge.py convention):
#   unset / "0" / "off" -> log only (no POST)
#   "1" / "on"          -> POST to delta-kernel /api/signals
DELTA_KERNEL_URL = os.environ.get("DELTA_KERNEL_URL", "http://localhost:3001")
SIGNAL_EMIT_ENABLED = os.environ.get("OPTOGON_SIGNAL_EMIT", "").strip().lower() in {"1", "on", "true"}

# Pacing
DEFAULT_TOKEN_BUDGET_PER_NODE = 200
MAX_QUESTIONS_PER_TURN = 1

# Inference
DEFAULT_CONFIDENCE_FLOOR = 0.7
AUTO_CONFIRM_CONFIDENCE = 0.85  # Above this, inferred values skip the question

# LLM
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("OPTOGON_LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_ENABLED = bool(ANTHROPIC_API_KEY)


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PATHS_DIR.mkdir(parents=True, exist_ok=True)
