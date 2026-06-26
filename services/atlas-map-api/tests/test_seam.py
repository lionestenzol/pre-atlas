"""Tests for the perceive -> compile -> carry integration seam (SEAM #1).

All deterministic — no network, no real subprocess:
  1. build_argv positional `{param}` substitution — the gateway change that makes
     positional-arg tools (sigil) reachable, with every safety invariant preserved.
  2. declared_params sees cli placeholders (so the enforcer ALLOWS the arg).
  3. The sigil overlay is a well-formed cli surface.
  4. Receipt.from_envelope — the connective currency: gateway envelope -> ONE shape,
     lifting sigil's sha256 join key.
  5. Hermetic end-to-end: call_capability through a faked subprocess (no sigil
     install needed) -> envelope -> Receipt.
"""

from __future__ import annotations

import asyncio
import subprocess

import pytest

from atlas_map_api import describe as d
from atlas_map_api import gateway
from atlas_map_api.loader import load_snapshot
from atlas_map_api.seam import SEAM_VERSION, Receipt


# ---- gateway: positional {param} substitution (the enabling change) -----------
def test_build_argv_positional_substitution():
    argv, err = gateway.build_argv("sigil info {input}", {"input": "C:/x/s.sgl"})
    assert err is None
    assert argv == ["sigil", "info", "C:/x/s.sgl"]  # positional — no sentinel, no flags


def test_build_argv_positional_plus_leftover_flag():
    argv, err = gateway.build_argv("tool {a}", {"a": "1", "b": "2"})
    assert err is None
    assert argv == ["tool", "1", "--", "--b", "2"]  # {a} bound positionally; b trails as a flag


def test_build_argv_unbound_placeholder_fails_loud():
    argv, err = gateway.build_argv("sigil info {input}", {})
    assert argv == [] and err is not None and "input" in err


def test_build_argv_positional_value_is_charset_checked():
    # a SUBSTITUTED positional is held to the same no-injection rules as a flag value.
    for bad in ({"input": "a; rm -rf /"}, {"input": "$(whoami)"}, {"input": "a`b`"}, {"input": "a|b"}):
        argv, err = gateway.build_argv("sigil info {input}", bad)
        assert argv == [] and err is not None


def test_build_argv_positional_value_rejects_leading_dash():
    argv, err = gateway.build_argv("sigil info {input}", {"input": "-rf"})
    assert argv == [] and err is not None


def test_build_argv_rejects_placeholder_as_executable():
    # defense-in-depth: argv[0] (the binary) must be a literal, never caller-chosen.
    argv, err = gateway.build_argv("{cmd} info", {"cmd": "python"})
    assert argv == [] and err is not None and "literal" in err


def test_build_argv_backward_compat_flag_sentinel():
    # the pre-existing `--key value` behaviour (no placeholder) is unchanged.
    assert gateway.build_argv("atlas where", {"limit": "5"}) == (["atlas", "where", "--", "--limit", "5"], None)


# ---- gateway: declared_params sees cli placeholders ---------------------------
def test_declared_params_finds_cli_positional():
    assert gateway.declared_params("sigil info {input}", ()) == {"input"}


def test_declared_params_http_path_unchanged():
    assert gateway.declared_params("GET /describe/{surface}?role=R", ()) == {"surface"}
    assert gateway.declared_params("POST /items/{id}/status", ("status",)) == {"id", "status"}


# ---- the sigil overlay is registered + well-formed ----------------------------
def test_sigil_overlay_is_a_cli_surface():
    snap = load_snapshot()
    ov = d.load_overlay(snap.repo_root, "sigil")
    assert ov is not None and ov.kind == "cli"
    info = next(c for c in ov.capabilities if c.id == "info")
    assert info.invoke == "sigil info {input}" and "input" in info.needs
    assert gateway.declared_params(info.invoke, info.needs) == {"input"}
    # pack/unpack write files -> labelled write so they are double-gated.
    assert all(c.direction == "write" for c in ov.capabilities if c.id in ("pack", "unpack"))


# ---- Receipt: the connective currency -----------------------------------------
FIXED_TS = "2026-06-26T00:00:00+00:00"
SHA = "9f17f0f291c870ff84f2f027077687b340bf04168c8d3b2f1b653995afc7d548"


def test_receipt_defaults_seam_version_and_is_frozen():
    r = Receipt(tool="sigil", produced_at=FIXED_TS, status="ok")
    assert r.seam_version == SEAM_VERSION
    with pytest.raises(Exception):
        r.tool = "x"  # frozen -> immutable per coding-style


def test_from_cli_envelope_parses_stdout_and_lifts_sha():
    env = {
        "ok": True, "code": 200, "surface": "sigil", "capability": "info", "kind": "cli",
        "status": 0, "data": {"stdout": f'{{"op": "info", "sha256": "{SHA}"}}', "stderr": ""},
        "error": None, "meta": {},
    }
    r = Receipt.from_envelope(env, produced_at=FIXED_TS)
    assert r.status == "ok" and r.tool == "sigil"
    assert r.sha256 == SHA                            # join key lifted from the tool's own receipt
    assert r.data == {"op": "info", "sha256": SHA}    # structured payload, not a stdout blob


def test_caller_sha_is_authoritative_over_stdout():
    env = {"ok": True, "surface": "sigil", "data": {"stdout": '{"sha256": "aaa"}', "stderr": ""}, "error": None}
    r = Receipt.from_envelope(env, produced_at=FIXED_TS, sha256="bbb")
    assert r.sha256 == "bbb"


def test_failed_call_becomes_error_status():
    env = {"ok": False, "surface": "sigil", "kind": "cli", "data": {"stdout": "", "stderr": "boom"}, "error": "exit 1"}
    r = Receipt.from_envelope(env, produced_at=FIXED_TS)
    assert r.status == "error" and r.error == "exit 1"


def test_refusal_becomes_error_receipt():
    refusal = {"refusal": True, "ok": False, "code": 501,
               "error": "cli invocation is gated off (set DESCRIBE_GATEWAY_CLI=1)"}
    r = Receipt.from_envelope({**refusal, "surface": "sigil"}, produced_at=FIXED_TS)
    assert r.status == "error" and "gated off" in r.error and r.tool == "sigil"


def test_http_envelope_passes_data_through():
    env = {"ok": True, "surface": "delta-kernel", "kind": "http", "data": {"status": "ok"}, "error": None}
    r = Receipt.from_envelope(env, produced_at=FIXED_TS)
    assert r.status == "ok" and r.data == {"status": "ok"} and r.sha256 is None


# ---- hermetic end-to-end: call_capability -> envelope -> Receipt --------------
def test_seam_end_to_end_through_gateway(monkeypatch):
    """The WHOLE chain without a real sigil install: enforce -> build_argv positional
    -> _invoke_cli (faked subprocess) -> normalized envelope -> Receipt + join key."""
    stdout = f'{{"op": "info", "magic": "SGL1", "sha256": "{SHA}", "container_len": 155}}'
    monkeypatch.setattr(gateway, "CLI_ENABLED", True)
    monkeypatch.setattr(gateway.shutil, "which", lambda exe: f"/fake/bin/{exe}")

    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(gateway.subprocess, "run", fake_run)

    snap = load_snapshot()
    env = asyncio.run(gateway.call_capability(
        snap, "sigil", "info", {"input": "C:/x/sample.sgl"}, token=None, role_name="root",
    ))
    # positional bound: exe abs-resolved, value passed positionally (no flag, no sentinel)
    assert captured["argv"][1:] == ["info", "C:/x/sample.sgl"]
    r = Receipt.from_envelope(env, produced_at=FIXED_TS)
    assert r.status == "ok" and r.sha256 == SHA and r.tool == "sigil"
