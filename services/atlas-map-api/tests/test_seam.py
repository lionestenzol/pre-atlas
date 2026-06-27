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


def test_lifecycle_receipts_chain_on_one_join_key():
    """pack -> info -> unpack: three sigil capabilities, three stdout receipts, ONE
    sha256. The seam lifts the same join key from each, so a chain keys on it in
    either direction. Receipt shapes mirror sigil.py cmd_pack/cmd_info/cmd_unpack;
    unpack now self-describes (container_bytes/ratio) symmetric with pack."""
    def cli_env(cap: str, stdout: str) -> dict:
        return {"ok": True, "surface": "sigil", "capability": cap, "kind": "cli",
                "status": 0, "data": {"stdout": stdout, "stderr": ""}, "error": None, "meta": {}}

    pack = f'{{"op": "pack", "carrier": "sgl", "sha256": "{SHA}", "ratio": 17.35, "dict_id": 0}}'
    info = f'{{"op": "info", "magic": "SGL1", "sha256": "{SHA}", "container_len": 122}}'
    unpack = f'{{"op": "unpack", "sha256": "{SHA}", "container_bytes": 122, "ratio": 17.35, "verified": true}}'

    receipts = [Receipt.from_envelope(cli_env(c, s), produced_at=FIXED_TS)
                for c, s in (("pack", pack), ("info", info), ("unpack", unpack))]
    assert all(r.status == "ok" and r.tool == "sigil" for r in receipts)
    assert {r.sha256 for r in receipts} == {SHA}          # one join key across the whole lifecycle
    assert receipts[2].data["container_bytes"] == 122      # carry receipt self-describes like pack
    assert receipts[2].data["ratio"] == 17.35


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


# ---- the fan-out: binre / gw / st3gg / delta-scp-demo --------------------------
def test_fanout_overlays_are_wellformed():
    """The 4 fan-out surfaces load with the right kind and a resolvable invoke."""
    snap = load_snapshot()

    binre = d.load_overlay(snap.repo_root, "binre")
    rep = next(c for c in binre.capabilities if c.id == "report")
    assert binre.kind == "cli" and rep.direction == "read"
    assert rep.invoke == "python tools/binre/report.py {target}"   # path relative to repo_root (gateway cwd)
    assert gateway.declared_params(rep.invoke, rep.needs) == {"target"}

    gw = d.load_overlay(snap.repo_root, "groundwork-cli")
    idx = next(c for c in gw.capabilities if c.id == "index")
    assert gw.kind == "cli" and idx.direction == "write"           # writes .groundwork/ -> double-gated
    assert gateway.declared_params(idx.invoke, idx.needs) == {"root"}

    st = d.load_overlay(snap.repo_root, "st3gg")
    an = next(c for c in st.capabilities if c.id == "analyze")
    assert st.kind == "cli" and an.direction == "read"             # analyze only; decode is NOT exposed
    assert gateway.declared_params(an.invoke, an.needs) == {"input"}
    assert "decode" not in {c.id for c in st.capabilities}         # injection channel stays off the seam

    dscp = d.load_overlay(snap.repo_root, "delta-scp-demo")
    assert dscp.kind == "http"                                     # name MUST match launch.json -> port 3012
    assert {c.invoke for c in dscp.capabilities} == {"GET /healthz", "GET /jobs/{id}"}

    # perceive-stage wrappers (binre-style thin adapters over ~/.claude skill engines)
    cr = d.load_overlay(snap.repo_root, "code-recon")
    orient = next(c for c in cr.capabilities if c.id == "orient")
    assert cr.kind == "cli" and orient.direction == "read"        # runs orient WITHOUT --regen
    assert gateway.declared_params(orient.invoke, orient.needs) == {"root"}

    ri = d.load_overlay(snap.repo_root, "repo-inventory")
    inv = next(c for c in ri.capabilities if c.id == "inventory")
    assert ri.kind == "cli" and inv.direction == "read"
    assert gateway.declared_params(inv.invoke, inv.needs) == {"root"}


def test_fanout_receipts_lift_each_tools_join_key():
    """binre/gw/st3gg each print a stdout JSON receipt carrying sha256; the seam
    Receipt lifts it as the join key. Shapes mirror the live proofs."""
    def cli_env(surface: str, stdout: str) -> dict:
        return {"ok": True, "surface": surface, "kind": "cli", "status": 0,
                "data": {"stdout": stdout, "stderr": ""}, "error": None, "meta": {}}

    cases = {
        "binre": f'{{"tool":"binre","op":"report","sha256":"{SHA}","found":true}}',
        "groundwork-cli": f'{{"tool":"gw","op":"index","sha256":"{SHA}","subsystem_count":1}}',
        "st3gg": f'{{"tool":"st3gg","op":"analyze","sha256":"{SHA}","analysis":{{}}}}',
        "code-recon": f'{{"tool":"code-recon","op":"orient","sha256":"{SHA}","verdict":"FRESH","found":true}}',
        "repo-inventory": f'{{"tool":"repo-inventory","op":"inventory","sha256":"{SHA}","system_count":3,"found":true}}',
    }
    for surface, stdout in cases.items():
        r = Receipt.from_envelope(cli_env(surface, stdout), produced_at=FIXED_TS)
        assert r.status == "ok" and r.sha256 == SHA, f"{surface} did not lift the join key"
        assert r.tool == surface


# ---- the standalone `seam` runner ---------------------------------------------
def _load_seam_runner(snap):
    import importlib.util
    runpy = snap.repo_root / "tools" / "seam" / "run.py"
    spec = importlib.util.spec_from_file_location("seam_run", runpy)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                 # main() is __main__-gated -> not executed on import
    return mod


def test_seam_runner_helpers_and_pipeline():
    """The model-agnostic runner's pure helpers behave, and its perceive pipeline only
    references surfaces/capabilities that are actually registered."""
    snap = load_snapshot()
    seam = _load_seam_runner(snap)
    assert seam._summary([{"status": "ok"}, {"status": "error"}]) == {"ok": 1, "error": 1, "total": 2}
    assert seam._parse_kv(["root=C:/x", "target=abc"]) == {"root": "C:/x", "target": "abc"}
    for surface, cap, _arg in seam.PERCEIVE:
        ov = d.load_overlay(snap.repo_root, surface)
        assert ov is not None and cap in {c.id for c in ov.capabilities}, f"{surface}.{cap} not registered"


# ---- the lattice stages: CARRY (repomix) + NARRATE (deepwiki) ------------------
def test_carry_narrate_overlays_are_wellformed():
    """The two new lattice surfaces load as read-only cli with a resolvable invoke."""
    snap = load_snapshot()

    rmx = d.load_overlay(snap.repo_root, "repomix")
    pack = next(c for c in rmx.capabilities if c.id == "pack")
    assert rmx.kind == "cli" and pack.direction == "read"          # writes only its own .seam/ cache
    assert pack.invoke == "python tools/repomix/pack.py {root}"    # repo-root-relative, forward slashes
    assert gateway.declared_params(pack.invoke, pack.needs) == {"root"}

    dw = d.load_overlay(snap.repo_root, "deepwiki")
    nar = next(c for c in dw.capabilities if c.id == "narrate")
    assert dw.kind == "cli" and nar.direction == "read"            # cached-wiki read only; live RAG not exposed
    assert nar.invoke == "python tools/deepwiki/ask.py {repo}"
    assert gateway.declared_params(nar.invoke, nar.needs) == {"repo"}
    assert "ask" not in {c.id for c in dw.capabilities}            # the slow live lane stays off the seam


def test_carry_narrate_pipelines_only_reference_registered_surfaces():
    """seam CARRY/NARRATE stages point only at surfaces+caps that are actually registered."""
    snap = load_snapshot()
    seam = _load_seam_runner(snap)
    assert set(seam.PIPELINES) == {"perceive", "carry", "narrate"}
    for stage in (seam.CARRY, seam.NARRATE):
        for surface, cap, _arg in stage:
            ov = d.load_overlay(snap.repo_root, surface)
            assert ov is not None and cap in {c.id for c in ov.capabilities}, f"{surface}.{cap} not registered"


def test_carry_receipt_lifts_repomix_join_key():
    """repomix pack prints a stdout JSON receipt with sha256; the seam Receipt lifts it."""
    env = {"ok": True, "surface": "repomix", "kind": "cli", "status": 0,
           "data": {"stdout": f'{{"tool":"repomix","op":"pack","sha256":"{SHA}","found":true,'
                              f'"file_count":2,"char_count":5777}}', "stderr": ""},
           "error": None, "meta": {}}
    r = Receipt.from_envelope(env, produced_at=FIXED_TS)
    assert r.status == "ok" and r.sha256 == SHA and r.tool == "repomix"


def test_narrate_absence_is_ok_receipt_without_join_key():
    """A repo with no cached wiki -> found:false, exit 0: an ok Receipt with NO join key
    (the legitimate-absence case, like code-recon orient MISSING)."""
    env = {"ok": True, "surface": "deepwiki", "kind": "cli", "status": 0,
           "data": {"stdout": '{"tool":"deepwiki","op":"wiki","found":false,'
                              '"reason":"no cached wiki for this repo"}', "stderr": ""},
           "error": None, "meta": {}}
    r = Receipt.from_envelope(env, produced_at=FIXED_TS)
    assert r.status == "ok" and r.sha256 is None and r.tool == "deepwiki"


def test_deepwiki_wrapper_content_addresses_a_cached_wiki(monkeypatch):
    """Hermetic proof of the found:true NARRATE path: a cached wiki is read and
    content-addressed, the sha is STABLE across volatile-field changes (no live backend)."""
    import importlib.util
    import io
    import json as _json
    snap = load_snapshot()
    askpy = snap.repo_root / "tools" / "deepwiki" / "ask.py"
    spec = importlib.util.spec_from_file_location("deepwiki_ask", askpy)
    ask = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ask)

    wiki = {"wiki_structure": {"title": "demo", "pages": [{"id": "p1", "content": "x"}]},
            "generated_pages": {"p1": "x"}}

    def fake_urlopen(url, timeout=0):
        body = dict(wiki)
        body["generated_at"] = "2026-06-27T10:00:00Z"  # volatile -> must NOT affect the sha
        return io.BytesIO(_json.dumps(body).encode())

    monkeypatch.setattr(ask.urllib.request, "urlopen", fake_urlopen)
    r1 = ask.read_wiki("https://github.com/o/r")
    assert r1["found"] is True and isinstance(r1["sha256"], str) and r1["page_count"] == 1

    # a different volatile timestamp yields the SAME content-address (scrubbed before hashing)
    def fake_urlopen2(url, timeout=0):
        body = dict(wiki)
        body["generated_at"] = "2099-01-01T00:00:00Z"
        return io.BytesIO(_json.dumps(body).encode())
    monkeypatch.setattr(ask.urllib.request, "urlopen", fake_urlopen2)
    r2 = ask.read_wiki("https://github.com/o/r")
    assert r2["sha256"] == r1["sha256"], "content-address must ignore volatile timestamps"


# ---- objective combo feed: seam manifest -> tool-outcome ledger ----------------
def _perceive_manifest(all_ok: bool) -> dict:
    """A synthetic perceive manifest (3 tools) mirroring run.py's manifest shape."""
    recs = [
        {"tool": "repo-inventory", "status": "ok", "sha256": SHA, "error": None},
        {"tool": "code-recon", "status": "ok", "sha256": SHA, "error": None},
        {"tool": "groundwork-cli",
         "status": "ok" if all_ok else "error",
         "sha256": SHA if all_ok else None,
         "error": None if all_ok else "writes gated"},
    ]
    err = sum(1 for r in recs if r["status"] != "ok")
    return {"pipeline": "perceive", "target": "C:/x/repo", "produced_at": FIXED_TS,
            "receipts": recs, "summary": {"ok": len(recs) - err, "error": err, "total": len(recs)}}


def test_seam_ledger_feed_is_gated_off_by_default(tmp_path, monkeypatch):
    """No SEAM_LEDGER -> the appender is a no-op and never touches the ledger file."""
    snap = load_snapshot()
    seam = _load_seam_runner(snap)
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.delenv("SEAM_LEDGER", raising=False)
    assert seam._append_ledger(_perceive_manifest(all_ok=True)) == 0
    assert not ledger.exists()                       # unit/exploratory runs never pollute the ledger


def test_seam_ledger_feed_writes_objective_cofire_rows(tmp_path, monkeypatch):
    """SEAM_LEDGER=1 -> one row per tool, shared session+turn key, OBJECTIVE reward,
    in exactly the shape combo.py's cofire grouping consumes (session+request -> turn,
    distinct skills -> a co-fire, reward_score = all-receipts-ok)."""
    import json as _json
    snap = load_snapshot()
    seam = _load_seam_runner(snap)
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SEAM_LEDGER", "1")

    n = seam._append_ledger(_perceive_manifest(all_ok=True))
    assert n == 3                                    # one row per receipt
    rows = [_json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 3
    # the cofire contract combo.py relies on:
    assert {r["session"] for r in rows} == {"seam:perceive:C:/x/repo"}          # one session
    assert {r["request"] for r in rows} == {"seam:perceive:C:/x/repo"}          # one turn key
    assert {r["skill"] for r in rows} == {"repo-inventory", "code-recon", "groundwork-cli"}
    assert [r["invocation_index"] for r in rows] == [0, 1, 2]                   # monotonic block
    assert all(r["reward_score"] == 1.0 and r["source"] == "seam" for r in rows)  # objective +1

    # a re-run of the SAME pipeline+target continues the invocation_index block (monotonic)
    seam._append_ledger(_perceive_manifest(all_ok=True))
    rows2 = [_json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [r["invocation_index"] for r in rows2[-3:]] == [3, 4, 5]


def test_seam_ledger_feed_penalizes_a_failed_combination(tmp_path, monkeypatch):
    """Any receipt in error -> the whole combination scores -1 (objective, not sentiment)."""
    import json as _json
    snap = load_snapshot()
    seam = _load_seam_runner(snap)
    ledger = tmp_path / "tool-outcomes.jsonl"
    monkeypatch.setenv("SEAM_LEDGER_PATH", str(ledger))
    monkeypatch.setenv("SEAM_LEDGER", "1")
    seam._append_ledger(_perceive_manifest(all_ok=False))
    rows = [_json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert all(r["reward_score"] == -1.0 and r["reward"] == "objective_error" for r in rows)
