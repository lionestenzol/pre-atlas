import importlib
import os
import subprocess
import sys
import tempfile

import pytest


def test_llm_agent_demo_importable():
    mod = importlib.import_module("shardstate.examples.llm_agent_demo")
    assert hasattr(mod, "main")
    assert hasattr(mod, "MockLLM")
    assert hasattr(mod, "ResearcherAgent")
    assert hasattr(mod, "VerifierAgent")


def test_llm_agent_demo_runs_to_completion(capsys):
    from shardstate.examples import llm_agent_demo

    with tempfile.TemporaryDirectory() as d:
        result = llm_agent_demo.main(db_dir=d)
    assert isinstance(result, dict)
    assert result["state_hash"]
    assert len(result["state_hash"]) > 16
    assert result["entities"]
    for v in result["entities"].values():
        assert v["type"] == "fact"
        assert v["verified"] in (True, False)
        assert v["reason"]


def test_mock_llm_deterministic():
    from shardstate.examples.llm_agent_demo import MockLLM

    llm = MockLLM()
    a = llm.decide("p", {"role": "researcher", "claim": "x", "source": "s"})
    b = llm.decide("p", {"role": "researcher", "claim": "x", "source": "s"})
    assert a == b


def test_mcp_client_demo_importable():
    mod = importlib.import_module("shardstate.examples.mcp_client_demo")
    assert hasattr(mod, "main")


def test_mcp_client_demo_handles_missing_mcp():
    # Run as subprocess with a fake import path that hides mcp if installed.
    # Simpler: just call main() — it should return 0 whether or not mcp is present.
    from shardstate.examples import mcp_client_demo

    # If mcp is available the demo will spawn a subprocess; skip that path here
    # by monkey-patching _check_mcp to simulate the missing-dep path.
    original = mcp_client_demo._check_mcp
    try:
        mcp_client_demo._check_mcp = lambda: False
        rc = mcp_client_demo.main()
        assert rc == 0
    finally:
        mcp_client_demo._check_mcp = original


def test_llm_agent_demo_runnable_via_module(tmp_path):
    # Smoke check that `python -m shardstate.examples.llm_agent_demo` exits cleanly.
    proc = subprocess.run(
        [sys.executable, "-m", "shardstate.examples.llm_agent_demo"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "final state hash" in proc.stdout
