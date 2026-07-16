"""Tests for the headless, caller-scoped self-description ('test form') layer.

Projection-logic assertions run against a SYNTHETIC fixture overlay (a fully
controlled criticality 0-3 surface) so they don't drift with live service data.
Enforcement + existence-hash assertions run against the real on-disk overlays.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas_map_api import auth
from atlas_map_api import describe as d
from atlas_map_api.loader import load_snapshot
from atlas_map_api.server import app

client = TestClient(app)


# A controlled surface spanning every exposure + criticality level.
FIXTURE = d.SurfaceOverlay(
    "demo",
    "Demo surface",
    (
        d.Capability("status", "Check status", "read", "public", 0, "GET /healthz"),
        d.Capability("view_queue", "View queue", "read", "agent", 0, "GET /q"),
        d.Capability("add_item", "Add item", "write", "agent", 1, "POST /q", ("title",)),
        d.Capability("mark_done", "Mark done", "write", "agent", 1, "POST /q/done", ("id",)),
        d.Capability("reindex", "Reindex", "write", "internal", 2, "POST /admin/reindex"),
        d.Capability("purge", "Purge", "write", "internal", 3, "POST /admin/purge"),
    ),
)


def _form(role_name: str) -> dict:
    return d.describe_surface(FIXTURE, d.ROLES[role_name])


# ---- the core property: same surface, different form per test-taker ----------
def test_different_roles_get_different_forms():
    anon, agent, root = _form("anon"), _form("agent"), _form("root")
    assert anon["totals"]["visible"] < agent["totals"]["visible"] < root["totals"]["visible"]
    assert anon["form_id"] == "demo@anon"
    assert agent["form_id"] == "demo@agent"


def test_anon_sees_only_public_read():
    form = _form("anon")
    assert [f["id"] for f in form["fields"]] == ["status"]
    assert form["redacted"] == 5
    assert form["locked"] == []


def test_agent_gets_agent_capabilities_but_not_internal():
    form = _form("agent")
    assert {f["id"] for f in form["fields"]} == {"status", "view_queue", "add_item", "mark_done"}
    assert form["redacted"] == 2  # reindex + purge are internal-exposure


def test_readonly_agent_cannot_see_write_actions():
    form = _form("agent-ro")
    assert {f["id"] for f in form["fields"]} == {"status", "view_queue"}
    assert all(f["direction"] == "read" for f in form["fields"])


# ---- the safety inversion: more critical => fewer descriptors -----------------
def test_critical_capability_is_locked_one_step_below_clearance():
    form = _form("operator")  # clearance 2 sees purge (criticality 3) as LOCKED
    locked_ids = {item["id"] for item in form["locked"]}
    assert "purge" in locked_ids
    for item in form["locked"]:
        assert "invoke" not in item  # locked never leaks how to call it


def test_root_sees_everything_including_destructive():
    form = _form("root")
    ids = {f["id"] for f in form["fields"]}
    assert "purge" in ids
    assert form["redacted"] == 0 and form["locked"] == []
    purge = next(f for f in form["fields"] if f["id"] == "purge")
    assert purge["invoke"] == "POST /admin/purge"


def test_full_fields_carry_invoke_lower_does_not_leak_it():
    add = next(f for f in _form("agent")["fields"] if f["id"] == "add_item")
    assert add["invoke"] == "POST /q" and add["needs"] == ["title"]


# ---- existence-hash hardening -------------------------------------------------
def test_existence_hash_stable_and_non_reversible():
    h1 = d.existence_hash("demo", "purge", "secret-A")
    h2 = d.existence_hash("demo", "purge", "secret-A")
    assert h1 == h2 and len(h1) == 12
    assert h1 != "purge" and "/admin/purge" not in h1
    assert d.existence_hash("demo", "purge", "secret-B") != h1  # secret-keyed


def test_redacted_proofs_only_for_critical_redactions():
    # anon redacts all 5 non-public; crit>=2 among them = reindex(2) + purge(3) => 2 proofs.
    form = d.describe_surface(FIXTURE, d.ROLES["anon"], secret="server-secret")
    assert len(form["redacted_proofs"]) == 2
    assert all(len(p) == 12 for p in form["redacted_proofs"])


def test_no_secret_means_no_proofs():
    form = d.describe_surface(FIXTURE, d.ROLES["anon"])
    assert form["redacted_proofs"] == []


# ---- role resolution + narrowing ---------------------------------------------
def test_unknown_role_falls_back_to_least_privileged():
    assert d.resolve_role("druid").name == "anon"
    assert d.resolve_role(None).name == "anon"
    assert d.resolve_role("ROOT").name == "root"


def test_narrow_role_can_only_narrow_never_escalate():
    root = d.ROLES["root"]
    anon = d.ROLES["anon"]
    assert d.narrow_role(root, "agent").name == "agent"   # root may preview agent
    assert d.narrow_role(anon, "root").name == "anon"     # anon may NOT become root
    assert d.narrow_role(anon, None).name == "anon"       # default = token role


# ---- auth: token -> role ------------------------------------------------------
def test_resolve_caller_role_no_token_is_anon():
    repo = load_snapshot().repo_root
    assert auth.resolve_caller_role(None, repo) == "anon"
    assert auth.resolve_caller_role("bogus-token", repo) == "anon"


def test_resolve_caller_role_write_token_is_root():
    repo = load_snapshot().repo_root
    assert auth.resolve_caller_role(auth.current_token(), repo) == "root"


# ---- endpoints: enforcement (real delta-kernel overlay) -----------------------
def test_no_token_role_root_still_yields_anon_form():
    # the headline security property: ?role=root cannot escalate an unauth caller.
    r = client.get("/describe/delta-kernel?role=root")
    assert r.status_code == 200
    body = r.json()
    assert body["form_id"] == "delta-kernel@anon"
    assert {f["id"] for f in body["fields"]} == {"health"}  # only the public read


def test_write_token_yields_root_form():
    r = client.get("/describe/delta-kernel", headers={"X-Atlas-Token": auth.current_token()})
    body = r.json()
    assert body["form_id"] == "delta-kernel@root"
    assert any(f["id"] == "override_law" for f in body["fields"])  # crit-3 visible to root


def test_write_token_can_narrow_to_agent():
    r = client.get(
        "/describe/delta-kernel?role=agent", headers={"X-Atlas-Token": auth.current_token()}
    )
    body = r.json()
    assert body["form_id"] == "delta-kernel@agent"
    ids = {f["id"] for f in body["fields"]}
    assert "override_law" not in ids and "set_state" not in ids  # internal hidden from agent


def test_endpoint_emits_existence_proofs_for_anon():
    body = client.get("/describe/delta-kernel").json()  # anon
    # set_state(crit2) + override_law(crit3) are internal -> redacted -> 2 proofs
    assert len(body["redacted_proofs"]) == 2


def test_describe_index_covers_all_35_surfaces():
    body = client.get("/describe").json()
    assert {"anon", "agent", "operator", "root"} <= {x["role"] for x in body["roles"]}
    expected = {
        # services (16) — mirofish/mosaic-dashboard/mosaic-orchestrator moved to
        # services/_retired/ and no longer declare overlays under services/.
        "aegis-fabric", "atlas-map-api", "canvas-engine", "cognitive-sensor", "cortex",
        "crucix", "delta-kernel", "droplist", "memory-hub", "openclaw", "optogon",
        "perception", "search-stack", "triangulation", "uasc-executor", "ws-gateway",
        # apps (7)
        "inpact", "lattice", "webos-333", "code-converter", "blueprint-generator",
        "ai-exec-pipeline", "canvas-demo",
        # tools (11) — +code-recon, +repo-inventory since this set was last updated
        "atlas-cli", "atlas-audit", "anatomy-extension", "anatomy-research",
        "anatomy-rewrite", "codex-partner", "fest-reconcile", "mini-ship", "reminders",
        "code-recon", "repo-inventory",
    }
    missing = expected - set(body["surfaces"])
    assert not missing, f"surfaces missing self-description overlays: {sorted(missing)}"
    assert len(expected) == 34


def test_describe_endpoint_text_narration():
    r = client.get("/describe/droplist?format=text")  # anon
    assert r.status_code == 200
    assert "You can:" in r.text


def test_describe_unknown_surface_404():
    assert client.get("/describe/does-not-exist?role=root").status_code == 404


def test_describe_state_none_without_live():
    assert client.get("/describe/delta-kernel").json()["state"] is None


def test_describe_live_populates_state():
    body = client.get("/describe/delta-kernel?live=1").json()
    assert body["state"] is not None and body["state"]["probed"] is True
    assert body["state"]["via"] == "health"  # probed the public health read
    assert "reachable" in body["state"]


# ---- triggers: the /route field ------------------------------------------------
def test_capability_from_dict_parses_triggers():
    cap = d.Capability.from_dict({
        "id": "digest", "label": "Digest", "direction": "read", "exposure": "public",
        "criticality": 0, "triggers": ["where am i", "catch me up"],
    })
    assert cap.triggers == ("where am i", "catch me up")


def test_capability_from_dict_defaults_triggers_to_empty():
    cap = d.Capability.from_dict({"id": "x", "label": "X", "direction": "read", "exposure": "public", "criticality": 0})
    assert cap.triggers == ()


def test_full_field_includes_triggers_only_when_present():
    overlay = d.SurfaceOverlay("x", "headline", (
        d.Capability("a", "A", "read", "public", 0, triggers=("hello",)),
        d.Capability("b", "B", "read", "public", 0),
    ))
    fields = d.describe_surface(overlay, d.ROLES["anon"])["fields"]
    by_id = {f["id"]: f for f in fields}
    assert by_id["a"]["triggers"] == ["hello"]
    assert "triggers" not in by_id["b"]


def test_render_text_no_actions_case():
    overlay = d.SurfaceOverlay("x", "headline", (
        d.Capability("secret", "Secret", "write", "internal", 3, "POST /x"),
    ))
    text = d.render_text(d.describe_surface(overlay, d.ROLES["anon"]))
    assert "no available actions" in text
