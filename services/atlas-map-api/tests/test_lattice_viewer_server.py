"""Tests for tools/lattice/viewer_server.py -- the Seq 6 live viewer's pure logic.

Only the backend's decision logic is unit-tested here (node-name
disambiguation, and the updates-stream filter that distinguishes a node
completion from its inner @task's raw return value -- both are easy to get
subtly wrong and would silently corrupt the browser's live view). The FastAPI
routes themselves were verified live in-browser (real demo run + real
code-recon call through the actual UI, confirmed via Cytoscape node classes
matching each step's real outcome) rather than re-tested here with a
TestClient, since SSE + background asyncio.create_task streaming is exactly
the kind of thing that looks right under a mocked test client but breaks for
real -- the browser run is the trustworthy proof for that part.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_lattice_module(name: str):
    path = Path("C:/Users/bruke/Pre Atlas/tools/lattice") / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"lattice_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


vs = _load_lattice_module("viewer_server")


def test_node_names_are_unique_for_repeated_skills():
    assert vs._node_names(["code-recon", "weapon"]) == ["code-recon", "weapon"]
    assert vs._node_names(["code-recon", "code-recon", "weapon"]) == \
        ["code-recon", "code-recon_2", "weapon"]


def test_is_node_update_true_only_for_the_state_patch_shape():
    # node-level update: {"receipts": [...]} -- this is what the browser should see
    assert vs._is_node_update({"receipts": [{"tool": "a", "status": "ok"}]}) is True
    # inner @task's raw return value -- same key name as the node, must be filtered OUT
    assert vs._is_node_update({"tool": "a", "status": "ok", "sha256": "x"}) is False
    assert vs._is_node_update({}) is False
    assert vs._is_node_update(None) is False
    assert vs._is_node_update("not a dict") is False


def test_demo_step_ok_returns_a_valid_receipt_shape():
    import asyncio
    # demo_step now lives in demo_steps.py (Seq 7 shares it with run_chain.py's
    # --demo flag) -- viewer_server imports it under the same name, re-verify
    # the import wiring here rather than just testing demo_steps.py in isolation.
    fn = vs.demo_step("x", delay=0)
    receipt = asyncio.run(fn())
    assert receipt["tool"] == "x"
    assert receipt["status"] == "ok"
    assert receipt["sha256"]


def test_demo_step_fail_returns_an_error_receipt():
    import asyncio
    fn = vs.demo_step("x", delay=0, fail=True)
    receipt = asyncio.run(fn())
    assert receipt["status"] == "error"
    assert receipt["sha256"] is None
