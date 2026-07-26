"""Triage -> DropList seam: drop an actionable triage result into the drop list.

When ``auto_triage`` proposes an action that requires work, this bridge POSTs it
to the DropList intake valve (``POST /api/drop`` on :3073), where the bouncer +
chainer turn it into a deduped Work Packet. This is the wire that connects the
loop/auto-triage arm to the capture->execution system.

Posture mirrors its siblings ``atlas_signal.emit_signal`` and ``cortex_bridge.emit``:

  * env-gated   — dormant unless ``DROPLIST_DROP_URL`` is set, so wiring it in
                  changes nothing until the operator opts in.
  * fail-soft   — never raises on a network/HTTP fault; a triage run must not die
                  because the drop list is down.
  * assemble    — adds NO classification/storage logic; the intake bouncer already
                  dedups (zero-delta) and noise-gates, so re-runs don't spam.
                  See ~/.claude/rules/common/assemble-first.md.

Activate with, e.g.::

    DROPLIST_DROP_URL=http://localhost:3073/api/drop

See ~/.claude/rules/common/code-as-furniture.md — no broken/dead wire left in place.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

# Actions that mean "nothing to do" — never become a drop.
_NON_ACTIONS = {"", "none", "no-op", "noop", "skip", "keep"}


def is_actionable(proposed_action: Optional[str]) -> bool:
    """True when the triage action represents real work worth capturing. Pure."""
    if not proposed_action:
        return False
    return proposed_action.strip().lower() not in _NON_ACTIONS


def build_raw_input(title: str, proposed_action: str, rationale: str = "") -> str:
    """Compose the human-readable drop text from triage fields. Pure, I/O-free.

    Shape: ``"<title>: <action> -- <rationale>"`` with graceful collapse when a
    field is missing. This is exactly the ``rawInput`` the intake webhook speaks.
    """
    title = (title or "").strip()
    action = (proposed_action or "").strip()
    rationale = (rationale or "").strip()
    head = f"{title}: {action}" if title and action else (action or title)
    return f"{head} -- {rationale}" if rationale else head


def drop(
    title: str,
    proposed_action: str,
    rationale: str = "",
    *,
    url: Optional[str] = None,
    timeout: float = 5.0,
) -> Optional[dict[str, Any]]:
    """POST an actionable triage result to DropList intake. Fail-soft + env-gated.

    Returns:
      ``None``  -- dormant (no ``url`` arg and no ``DROPLIST_DROP_URL``) OR the
                   action is non-actionable. The caller can treat None as "skipped".
      ``dict``  -- ``{"ok": True, ...intake response...}`` on success, or
                   ``{"ok": False, "error": ..., "raw_input": ...}`` on any fault.

    Never raises on a network/HTTP/JSON fault — by contract.
    """
    if not is_actionable(proposed_action):
        return None
    target = url or os.environ.get("DROPLIST_DROP_URL")
    if not target:
        return None  # dormant by default — set DROPLIST_DROP_URL to activate

    raw = build_raw_input(title, proposed_action, rationale)
    data = json.dumps({"rawInput": raw}).encode("utf-8")
    req = urllib.request.Request(
        target,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not isinstance(payload, dict):
            payload = {"response": payload}
        return {"ok": True, **payload}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc), "raw_input": raw}
