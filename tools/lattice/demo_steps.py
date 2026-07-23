"""Zero-cost synthetic StepFns, shared by viewer_server.py (Seq 6) and
run_chain.py's --demo flag (Seq 7).

Seq 7 needs to prove a real OS-process kill + delta-kernel-triggered resume
without spending real Claude Agent SDK budget on every kill/resume cycle
during verification -- these steps go through the exact same
build_chain_graph/AsyncSqliteSaver checkpointing as a real skill chain, they
just don't call an LLM.
"""
from __future__ import annotations

import asyncio
from typing import Any


def demo_step(name: str, *, delay: float = 0.8, fail: bool = False):
    async def _fn() -> dict[str, Any]:
        await asyncio.sleep(delay)
        if fail:
            return {"seam_version": "v1", "tool": name, "sha256": None, "produced_at": "",
                     "status": "error", "data": None, "error": "demo failure"}
        return {"seam_version": "v1", "tool": name, "sha256": "0" * 64, "produced_at": "",
                 "status": "ok", "data": {"demo": True}, "error": None}

    return _fn
