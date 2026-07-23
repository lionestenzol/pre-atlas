#!/usr/bin/env python3
"""
build_atlas_manifest.py — regenerate atlas-manifest.yaml from ground truth.

The manifest is an INTERFACE-FIRST map of all of Atlas (provides / consumes /
requires / seams / contracts) sized to upload to an LLM so it reasons about real
structure instead of guessing. This script keeps it HONEST OVER TIME: the
mechanical facts are re-derived every run; curated knowledge lives in an overlay.

DERIVED every run (auto-refreshes):
  - identity / loc / deps / framework   <- audit/system-index.json
  - runtime ports                       <- .claude/launch.json   (boot truth)
  - purposes / governance / seams       <- atlas-map.json
  - provides (route surface)            <- pure-Python route sweep of services/ + apps/
  - contract list                       <- contracts/schemas/*.json

CURATED (audit/manifest-overlay.yaml — small, stable, hand-maintained):
  - role labels, what each UI asks, store shapes, security flags,
    contract ownership, cross-repo nodes.

Run:  python audit/build_atlas_manifest.py            # writes ../atlas-manifest.yaml
      python audit/build_atlas_manifest.py --stdout   # print instead of write
      python audit/build_atlas_manifest.py --out X     # custom output path

Route extraction is a regex sweep (same altitude as the code-recon `rg` ladder),
not a per-language AST parse — deliberately, to stay self-contained and fast.
See ~/.claude/rules/common/code-as-furniture.md — this is the regenerable,
furniture-grade version of the once-hand-built manifest.
"""
from __future__ import annotations
import json, re, sys, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

REPO = Path(__file__).resolve().parent.parent
AUDIT = REPO / "audit"
SRC_GROUPS = ("services", "apps")          # where route-bearing code lives
CODE_EXT = {".py", ".ts", ".js", ".mjs", ".tsx", ".jsx"}
SKIP_DIR = {"node_modules", "dist", "__pycache__", "build", ".git", ".next", "venv", ".venv"}

# ---- compact YAML emission (inline flow for leaf dicts / short lists) --------
class Flow(dict): ...
class FlowList(list): ...
yaml.add_representer(Flow, lambda d, o: d.represent_mapping("tag:yaml.org,2002:map", o, flow_style=True))
yaml.add_representer(FlowList, lambda d, o: d.represent_sequence("tag:yaml.org,2002:seq", o, flow_style=True))

# ---- source loaders ---------------------------------------------------------
def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def load_yaml(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8"))

# ---- route sweep ------------------------------------------------------------
PY_DEC = re.compile(r'@(\w+)\.(get|post|put|delete|patch|websocket)\(\s*["\']([^"\']+)')
PY_APIROUTE = re.compile(r'@(\w+)\.api_route\(\s*["\']([^"\']+)')
PY_FLASK = re.compile(r'@(\w+)\.route\(\s*["\']([^"\']+)["\']([^)]*)')
EXPRESS = re.compile(r'\b(?:app|router|[A-Za-z_]\w*[Rr]outer)\.(get|post|put|delete|patch)\(\s*["\'`](/[^"\'`]*)')

def _skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_DIR:
        return True
    n = path.name
    if n.endswith((".bak.json", ".bak")) or "-data.js" in n or "_data.js" in n:
        return True
    if n.startswith("test_") or ".spec." in n or n.endswith(".test.ts") or "/tests/" in path.as_posix():
        return True
    return False

def sweep_routes(repo: Path) -> dict[str, set[str]]:
    """system_name -> set of 'METHOD /path' (verified from source)."""
    out: dict[str, set[str]] = {}
    for group in SRC_GROUPS:
        base = repo / group
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if f.suffix not in CODE_EXT or not f.is_file() or _skip(f):
                continue
            rel = f.relative_to(repo).as_posix().split("/")
            if len(rel) < 2:
                continue
            system = rel[1]                      # services/<system>/...  or apps/<system>/...
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            hits = out.setdefault(system, set())
            for m in PY_DEC.finditer(text):
                p = m.group(3)
                if p.startswith("/"):
                    hits.add(f"{m.group(2).upper()} {p}")
            for m in PY_APIROUTE.finditer(text):
                if m.group(2).startswith("/"):
                    hits.add(f"* {m.group(2)}")
            for m in PY_FLASK.finditer(text):
                p, tail = m.group(2), m.group(3)
                if not p.startswith("/"):
                    continue
                methods = re.findall(r'["\'](GET|POST|PUT|DELETE|PATCH)["\']', tail.upper())
                for meth in (methods or ["GET"]):
                    hits.add(f"{meth} {p}")
            for m in EXPRESS.finditer(text):
                hits.add(f"{m.group(1).upper()} {m.group(2)}")
    return {k: v for k, v in out.items() if v}

def group_provides(routes: set[str]):
    """Group routes by their primary path segment; flat list if few."""
    if len(routes) <= 6:
        return FlowList(sorted(routes, key=_route_key))
    groups: dict[str, list[str]] = {}
    for r in routes:
        path = r.split(" ", 1)[1]
        segs = [s for s in path.split("/") if s]
        if not segs:
            key = "root"
        elif segs[0] in ("api", "v1") and len(segs) >= 2:
            key = segs[1].strip("{}")
        else:
            key = segs[0].strip("{}")
        groups.setdefault(key, []).append(r)
    return {k: FlowList(sorted(v, key=_route_key)) for k, v in sorted(groups.items())}

def _route_key(r: str):
    meth, path = (r.split(" ", 1) + [""])[:2]
    return (path, meth)

# ---- runtime ports from launch.json ----------------------------------------
def runtime_ports(launch: dict):
    """Return (system_path -> port) for backends, plus the full config list."""
    configs = launch.get("configurations", [])
    return configs

def port_for(system_path: str, configs: list) -> int | None:
    def norm(s): return str(s).replace("\\", "/").rstrip("/")
    cands = [c for c in configs if norm(c.get("cwd", "")).endswith(system_path)]
    if not cands:
        cands = [c for c in configs
                 if any(system_path in norm(a) for a in c.get("runtimeArgs", []))]
    if not cands:
        return None
    def score(c):
        args = " ".join(str(a) for a in c.get("runtimeArgs", []))
        s = 0
        if any(k in args for k in ("uvicorn", "server", "main:app", ":app")): s += 2
        if "vite" in args or ("next" in args and "dev" in args): s -= 1
        if "http-server" in args: s -= 2
        return s
    cands.sort(key=lambda c: (-score(c), c.get("port", 99999)))
    return cands[0].get("port")

# ---- assembly ---------------------------------------------------------------
def derive_lifecycle(name, atlas_map, ov):
    if name in ov.get("lifecycle_overrides", {}):
        return ov["lifecycle_overrides"][name]
    if name in atlas_map.get("retired", []):
        return "retired (legacy)"
    gov = atlas_map.get("governance", {}).get(name)
    if gov:
        return f"{gov.get('automation','active')}"
    return "active"

def build():
    index = load_json(AUDIT / "system-index.json")
    atlas = load_json(REPO / "atlas-map.json")
    launch = load_json(REPO / ".claude" / "launch.json")
    ov = load_yaml(AUDIT / "manifest-overlay.yaml")
    configs = runtime_ports(launch)
    routes = sweep_routes(REPO)

    purposes = atlas.get("purposes", {})
    governance = atlas.get("governance", {})
    edges = [tuple(e) for e in atlas.get("service_edges", [])]
    hub = ov["meta"]["hub"]

    entries = {e["name"]: e for e in index["entries"]}
    owners = ov.get("contract_owners", {})

    # ---- systems (only the real service/app subsystems, not ops/spec dirs) ----
    systems: dict = {}
    swept_systems, no_rest = [], []
    drift = []
    for e in index["entries"]:
        if e["group"] not in ("services", "apps"):
            continue
        name = e["name"]
        # apps that are pure static UIs are surfaced under `surfaces`, not systems,
        # UNLESS they expose routes (code-converter, ai-exec-pipeline servers).
        rt = routes.get(name)
        if e["group"] == "apps" and not rt:
            continue
        rport = port_for(e["path"], configs)
        code_port = e.get("port")
        if rport and code_port and rport != code_port:
            drift.append(f"{name}: system-index port {code_port} -> runtime {rport} (launch.json)")
        node = {}
        node["class"] = Flow({"role": ov.get("roles", {}).get(name, e["group"][:-1]),
                              "lifecycle": derive_lifecycle(name, atlas, ov)})
        if name in governance:
            node["automation"] = f"{governance[name]['automation']} — {governance[name].get('note','')}"
        props = {"lang": e.get("language", "?")}
        if e.get("framework") and e["framework"] != "unknown":
            props["framework"] = e["framework"]
        props["port"] = rport or code_port or "—"
        props["loc"] = e.get("total_loc", 0)
        props["files"] = e.get("file_count", 0)
        node["props"] = Flow(props)
        node["purpose"] = ov.get("purposes_override", {}).get(name) or purposes.get(name, "")
        if name in ov.get("modules", {}):
            node["modules"] = FlowList(ov["modules"][name])
        if e.get("entry_points"):
            node["entry_points"] = FlowList(e["entry_points"])
        if name in ov.get("stores", {}):
            node["stores"] = [Flow(s) for s in ov["stores"][name]]
        # provides
        if rt:
            node["provides"] = group_provides(rt)
            swept_systems.append(name)
        elif name in ov.get("provides_note", {}):
            node["provides"] = ov["provides_note"][name]
            no_rest.append(name)
        # consumes = out-edges + curated extras
        out_edges = [t for (fr, t) in edges if fr == name]
        consumes = list(ov.get("consumes_extra", {}).get(name, [])) or [t for t in out_edges]
        if consumes:
            node["consumes"] = FlowList(consumes)
        if name in ov.get("requires", {}):
            node["requires"] = FlowList(ov["requires"][name])
        if owners.get(name):
            node["speaks"] = FlowList(owners[name])
        if name in ov.get("deps_notable", {}):
            node["deps_notable"] = FlowList(ov["deps_notable"][name])
        if name in ov.get("notes", {}):
            node["note"] = ov["notes"][name]
        systems[name] = node

    # ---- inject cross-repo / extra systems from overlay ----
    for name, node in ov.get("extra_systems", {}).items():
        n = {}
        for k, v in node.items():
            n[k] = Flow(v) if (k in ("class", "props") and isinstance(v, dict)) else (
                   FlowList(v) if isinstance(v, list) else v)
        systems[name] = n

    # ---- contracts ----
    schema_dir = REPO / "contracts" / "schemas"
    on_disk = sorted(p.stem for p in schema_dir.glob("*.json")) if schema_dir.exists() else []
    owned_flat = {c for lst in owners.values() for c in lst}
    strays = sorted(set(on_disk) - owned_flat)        # exist but unassigned
    missing = sorted(owned_flat - set(on_disk))        # assigned but file absent
    contracts = {
        "count": len(on_disk),
        "location": "contracts/schemas/",
        "by_owner": {k: FlowList(v) for k, v in owners.items()},
        "key_contracts": ov.get("key_contracts", {}),
    }

    # ---- seams ----
    ann = ov.get("seam_annotations", {})
    def edge_line(fr, to):
        a = ann.get(f"{fr}->{to}")
        return f"{fr} → {to}" + (f" : {a}" if a else "")
    into_hub = [edge_line(fr, to) for (fr, to) in edges if to == hub]
    other = [edge_line(fr, to) for (fr, to) in edges if to != hub]
    seams = {"into_hub": into_hub, "other": other,
             "cross_repo": ov.get("cross_repo_seams", [])}

    # ---- lifecycle flags ----
    retired = atlas.get("retired", [])
    gated = [s for s, g in governance.items() if g.get("automation") == "gated"]
    dormant = [s for s, g in governance.items() if g.get("automation") == "dormant"]
    dormant += [s for s, lc in ov.get("lifecycle_overrides", {}).items() if str(lc).startswith("dormant")]
    stub = [s for s, lc in ov.get("lifecycle_overrides", {}).items() if str(lc).startswith("stub")]
    flagged = set(retired) | set(gated) | set(dormant) | set(stub) | {hub}
    active = [n for n in systems if n not in flagged]
    lifecycle_flags = {
        "hub": FlowList([hub]),
        "active": FlowList(sorted(active)),
        "gated_default_off": FlowList(sorted(gated)),
        "dormant": FlowList(sorted(set(dormant))),
        "stub_do_not_build_on": FlowList(sorted(stub)),
        "retired_do_not_build_on": FlowList(sorted(retired)),
        "security_flags": FlowList(ov.get("security_flags", [])),
    }

    # ---- totals ----
    owned = [e for e in index["entries"] if e["group"] in ("services", "apps", "tools")
             and e["name"] != "anatomy-research"]
    owned_loc = sum(e.get("total_loc", 0) for e in owned)

    # ---- meta ----
    today = datetime.date.today().isoformat()
    meta = dict(ov["meta"])
    meta["totals"] = Flow({"systems_in_manifest": len(systems),
                           "services": sum(1 for e in index["entries"] if e["group"] == "services"),
                           "apps": sum(1 for e in index["entries"] if e["group"] == "apps"),
                           "owned_loc_approx": owned_loc, "contracts": len(on_disk)})
    meta["generated_at"] = today
    meta["generator"] = "audit/build_atlas_manifest.py (deterministic; edit audit/manifest-overlay.yaml for curated bits)"

    doc = {
        "meta": meta,
        "spine_loop": ov.get("spine_loop", {}),
        "runtime_ports": runtime_ports_section(configs, index, atlas),
        "systems": systems,
        "surfaces": ov.get("surfaces", {}),
        "contracts": contracts,
        "seams": seams,
        "data_artifacts": [Flow(d) for d in ov.get("data_artifacts", [])],
        "lifecycle_flags": lifecycle_flags,
        "verification": {
            "method": "mechanical facts derived per run; curated bits from audit/manifest-overlay.yaml. Route surface = regex sweep of source.",
            "provides_route_verified": FlowList(sorted(swept_systems)),
            "no_rest_surface": FlowList(sorted(no_rest)),
            "port_drift_resolved": FlowList(drift) if drift else "none",
            "contract_strays_unassigned": FlowList(strays) if strays else "none",
            "contract_missing_files": FlowList(missing) if missing else "none",
            "rebuild": "python audit/build_atlas_manifest.py",
        },
    }
    return doc

def runtime_ports_section(configs, index, atlas):
    backends, statics = {}, {}
    for c in configs:
        args = " ".join(str(a) for a in c.get("runtimeArgs", []))
        name, port = c.get("name"), c.get("port")
        if port is None:
            continue
        (statics if "http-server" in args else backends)[name] = port
    return {"backends": Flow(dict(sorted(backends.items(), key=lambda kv: kv[1]))),
            "static_shell_servers": Flow(dict(sorted(statics.items(), key=lambda kv: kv[1]))),
            "note": "Runtime ports from .claude/launch.json (boot truth). Overrides code-default drift in audit/system-index.json — see verification.port_drift_resolved."}

HEADER = """\
# =============================================================================
# atlas-manifest.yaml — Atlas system manifest (interface-first)
#
#   GENERATED FILE — do not hand-edit. Regenerate with:
#       python audit/build_atlas_manifest.py
#   Curated knowledge (UI calls, store shapes, contract ownership, roles) lives
#   in audit/manifest-overlay.yaml. Mechanical facts (ports, routes, loc, deps,
#   seams, contracts) are re-derived from system-index.json + atlas-map.json +
#   .claude/launch.json + a source route sweep every run.
#
# PURPOSE: one compact, complete map of ALL of Atlas, sized to upload to an LLM
#   so it reasons about real structure without cherry-picking. INTERFACE, not
#   implementation. Reads the filesystem (not git) — gitignored stores included.
# HOW TO READ: provides = API surface you can ASK · consumes = who it calls ·
#   requires = auth needed · speaks = contracts · port = RUNTIME (launch.json).
# =============================================================================
"""

def main():
    out = REPO / "atlas-manifest.yaml"
    to_stdout = "--stdout" in sys.argv
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    doc = build()
    body = yaml.dump(doc, sort_keys=False, allow_unicode=True, width=200, default_flow_style=False)
    text = HEADER + "\n" + body
    yaml.safe_load(text)  # self-check: must parse
    if to_stdout:
        sys.stdout.write(text)
    else:
        out.write_text(text, encoding="utf-8")
        v = doc["verification"]
        print(f"wrote {out}  ({text.count(chr(10))+1} lines, {len(text)} bytes, ~{len(text)//4} tokens)")
        print(f"systems={len(doc['systems'])}  route-verified={len(v['provides_route_verified'])}  "
              f"contracts={doc['contracts']['count']}  seams={sum(len(x) for x in doc['seams'].values())}")
        if v["contract_strays_unassigned"] != "none":
            print("  ⚠ unassigned contracts:", v["contract_strays_unassigned"])
        if v["contract_missing_files"] != "none":
            print("  ⚠ owned contracts missing on disk:", v["contract_missing_files"])

if __name__ == "__main__":
    main()
