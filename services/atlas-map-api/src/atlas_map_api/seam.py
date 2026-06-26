"""The connective currency of the perceive -> compile -> carry stack.

Every tool reached through the gateway speaks its own dialect on stdout — sigil's
JSON receipt, binre's report.json, ST3GG's analysis dict, groundwork's plan index.
The Receipt is the ONE shape they all normalize into, so a downstream stage can
consume ANY tool's output uniformly, keyed on a single content-address: sigil's
SGL1 sha256 (the only sound content-address in the fleet).

This is the only hand-roll the integration seam earns. Cross-tool normalization is
the layer's whole reason to exist — a generic envelope library would make this
WORSE, not just later, because the join-key lift + gateway-envelope mapping ARE the
product (see ~/.claude/rules/common/assemble-first.md, the "worse vs later" test).
Everything underneath is reused: zstandard/Pillow/hashlib in sigil, subprocess +
arg-safety in the gateway, pydantic here.

Contract: a Receipt is ALWAYS produced — a tool success, a reached-but-failed call,
and a gateway refusal all map to one shape, differing only in `status`/`error`. The
caller never has to branch on "did the gateway refuse vs did the tool fail"; it
reads `status` and, on success, `data` keyed by `sha256`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel

# Bump when the Receipt SHAPE changes so a consumer can refuse an unknown dialect
# (binre's report.json should carry the same marker — backlog #6).
SEAM_VERSION = "seam.v1"

Status = Literal["ok", "error"]


def utc_now_iso() -> str:
    """ISO-8601 UTC stamp for `produced_at`. Injected (not called inside the model)
    so receipts stay deterministic in tests — pass an explicit value there."""
    return datetime.now(timezone.utc).isoformat()


def _try_json(s: Any) -> Any:
    """Best-effort parse of a tool's stdout into its structured receipt; None if it
    isn't JSON (then the raw {stdout,stderr} blob is kept as-is)."""
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


class Receipt(BaseModel):
    """One normalized result from any seam tool. Frozen — immutable per coding-style."""

    model_config = {"frozen": True}

    seam_version: str = SEAM_VERSION
    tool: str                       # the surface that produced this (e.g. "sigil")
    sha256: str | None = None       # content-address join key (sigil SGL1 sha), if known
    produced_at: str                # ISO-8601 UTC, injected by the caller
    status: Status                  # "ok" | "error" — the only branch a consumer needs
    data: Any = None                # the tool's own payload (parsed JSON, or {stdout,stderr})
    error: str | None = None

    @classmethod
    def from_envelope(
        cls,
        env: dict[str, Any],
        *,
        produced_at: str | None = None,
        sha256: str | None = None,
    ) -> "Receipt":
        """Map a gateway envelope (`_envelope` OR `_refusal`) into a Receipt.

        - status is "ok" only when the envelope's own `ok` is True; a refusal and a
          reached-but-failed call both become "error" (the consumer reads ONE field).
        - For cli surfaces the gateway packs {stdout,stderr} into `data`; we parse the
          tool's JSON receipt out of stdout so `data` is structured, and lift its
          `sha256` as the join key when the caller didn't already supply one.
        - A caller-supplied `sha256` is authoritative (it IS the known join key) and
          always wins over a value lifted from stdout.
        """
        tool = str(env.get("surface") or "unknown")
        ok = bool(env.get("ok"))
        data = env.get("data")
        join = sha256

        if isinstance(data, dict) and "stdout" in data:
            parsed = _try_json(data.get("stdout"))
            if parsed is not None:
                data = parsed
                if join is None and isinstance(parsed, dict) and isinstance(parsed.get("sha256"), str):
                    join = parsed["sha256"]

        return cls(
            tool=tool,
            sha256=join,
            produced_at=produced_at or utc_now_iso(),
            status="ok" if ok else "error",
            data=data,
            error=env.get("error"),
        )
