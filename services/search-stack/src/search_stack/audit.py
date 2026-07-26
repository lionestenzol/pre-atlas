"""Append-only audit log — every request/response one JSON line."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .settings import DATA_DIR

LOG_PATH = DATA_DIR / "audit.jsonl"


def log(event: str, **fields: Any) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")
