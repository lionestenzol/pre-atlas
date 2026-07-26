"""Clock: a single time source the whole OS reads.

Real UTC by default. If DROPLIST_NOW is set (ISO 8601), that is "now" — which
lets the 7-day simulation advance time deterministically without waiting.
"""

from __future__ import annotations

import datetime as _dt
import os


def now() -> _dt.datetime:
    override = os.environ.get("DROPLIST_NOW")
    if override:
        try:
            return _dt.datetime.fromisoformat(override.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return _dt.datetime.utcnow()


def now_iso() -> str:
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return now().strftime("%Y-%m-%d")


def parse(iso: str) -> _dt.datetime | None:
    if not iso:
        return None
    try:
        return _dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def hours_since(iso: str) -> float:
    t = parse(iso)
    if t is None:
        return 0.0
    return (now() - t).total_seconds() / 3600.0
