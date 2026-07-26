"""
Phase 2 · Sequence 01 · seed_clusters_from_portfolio

Reads portfolio_evidence.json and groups items into topic clusters using
seed terms derived from observed portfolio names + MEMORY.md threads.

Output: festival_out/clusters_v0.json

Each cluster has: name, seed_terms (literal lowercased tokens to match),
rationale (why these terms), portfolio_hits (item names that matched).

Method: cluster names anchor to repeated tokens in the corpus. Hits are
case-insensitive substring matches on item.name. An item may match more
than one cluster (overlap noted in Phase 2 · Seq 03 validation).
"""

import json
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from _match import _compile_seed  # word-boundary regex compiled per seed

PORTFOLIO = ROOT / "portfolio_evidence.json"
OUT_V1 = ROOT / "festival_out" / "clusters_v0.json"
OUT_V2 = ROOT / "festival_out" / "clusters_v0_v2.json"
# Pick output: if --v2 arg present, write v2; else v1 path (back-compat for any caller).
OUT = OUT_V2 if "--v2" in sys.argv else OUT_V1

CLUSTERS = [
    {
        "name": "anatomy",
        "seed_terms": [
            "anatomy",
            "anatomy-v1",
            "anatomyv1",
            "anatomy-extension",
            "anatomy-research",
            "anatomy-rewrite",
            "anatomy-map",
            "anatomy-frame",
            "anatomy-sidecar",
        ],
        "rationale": (
            "DOM-capture + envelope schema arc · extension captures, "
            "research mines, rewrite consolidates, schema (AnatomyV1.v1.json) "
            "is the contract. Seeds taken from the 4 explicit anatomy-* "
            "tools + map skill + the anatomy-frame-sidecar referenced in "
            "MEMORY.md carbo-shrink."
        ),
    },
    {
        "name": "mb3d_fractals",
        "seed_terms": [
            "mb3d",
            "mb3d_anim_demo",
            "mb3d-blender",
            "mandelbulb",
            "mandelbulb3d",
            "mandelbulber",
            "mandelbulber2",
            "mandelbulber2_install",
            "m3p",
            "m3p-to-fract",
            "m3f",
            ".fract",
            "fractal-machine",
            "mandelbox",
            "raymarcher",
            "fragmentarium",
        ],
        "rationale": (
            "3D fractal rendering arc · MB3D family (.m3p/.m3f) + "
            "Mandelbulber 2 (.fract) + the Blender bridge addon. Seeds "
            "taken from the 7 portfolio repos (mandelbulb3d skill, "
            "mandelbulber2 skill, m3p-to-fract, mb3d-blender, "
            "mb3d_anim_demo, mandelbulber2_install, fractal-machine) plus "
            "format extensions that disambiguate the cluster from "
            "general 3D."
        ),
    },
    {
        "name": "audio_music",
        "seed_terms": [
            "strudel",
            "stemai",
            "surge",
            "surge-xt",
            "nih-plug",
            "airwindows",
            "musescore",
            "fl356",
            "fl 3",
            "fl3",
            "vst3",
            "vst",
            "daw",
            "midi",
            "synth",
            "sampler",
            "audio",
        ],
        "rationale": (
            "Live-coding (Strudel) · stem analysis (STEMai) · VST plugin "
            "modernization (surge-xt, nih-plug Rust bootstrap, airwindows "
            "vendor source) · FL Studio 3.5.6 CLI renderer (fl356, "
            "tracked in MEMORY.md) · MuseScore MCP. Generic terms (vst, "
            "midi, synth) included so co-occurrence scan picks up convo "
            "discussions that pre-date the named project."
        ),
    },
    {
        "name": "atlas_core",
        "seed_terms": [
            "atlas",
            "pre atlas",
            "pre-atlas",
            "delta-kernel",
            "delta kernel",
            "cognitive-sensor",
            "cognitive sensor",
            "cycleboard",
            "cortex",
            "optogon",
            "aegis",
            "aegis-fabric",
            "openclaw",
            "mirofish",
            "perception service",
            "perception layer",
            "perception module",
            "triangulation",
            "mosaic",
            "inpact",
            "in-pact",
            "blueprint-generator",
            "code-converter",
            "ai-exec-pipeline",
            "uasc",
            "ws-gateway",
            "polaris",
            "crucix",
            "governance",
        ],
        "rationale": (
            "The Pre Atlas substrate · 15 services + 6 apps + governance "
            "mode system + the public/private GitHub repos. Mode names "
            "(RECOVER/CLOSURE/MAINTENANCE/COMPOUND/SCALE) included so "
            "Phase 3 can join era against mode-mention density. POLARIS "
            "included per its MEMORY.md positioning as agent-execution "
            "layer."
        ),
    },
    {
        "name": "web_extract",
        "seed_terms": [
            "scrapling",
            "scraping",
            "sitepull",
            "web-audit",
            "web-extract",
            "competitor-monitor",
            "competitor monitor",
            "brightdata",
            "datadome",
            "cloudflare",
            "anti-bot",
            "playwright",
            "puppeteer",
            "headless",
            "humanize",
        ],
        "rationale": (
            "Web-extraction stack · Scrapling (cloned, smoke, official "
            "skill) · sitepull/web-audit (Node CLI sibling) · "
            "competitor-monitor (template + skill + MCP) · "
            "web-extract-workflow router skill. Anti-bot terms "
            "(brightdata, datadome, cloudflare) included so the cluster "
            "captures the managed-unlock-over-stealth doctrine threads "
            "from MEMORY.md."
        ),
    },
    {
        "name": "productivity_skills",
        "seed_terms": [
            "weapon",
            "festival",
            "mini-ship",
            "miniship",
            "autopilot",
            "project-finisher",
            "handoff",
            "handoff-out",
            "eval-harness",
            "cookbook",
            "search-first",
            "security-review",
            "strategic-compact",
            "tdd-workflow",
            "verification-loop",
            "coding-standards",
            "backend-patterns",
            "frontend-patterns",
            "wasp-patterns",
            "codex-delegate",
            "codex-partner",
            "continuous-learning",
            "slash command",
            "/weapon",
            "/fest",
            "/mini-ship",
            "/autopilot",
        ],
        "rationale": (
            "Meta-tooling cluster · Claude Code custom skills that "
            "automate or organize the dev loop itself. Weapon (autonomous "
            "exec), fest (festival project methodology), mini-ship "
            "(smallest-atom loop), autopilot (state-machine driver), "
            "project-finisher, plus the lower-traffic pattern skills "
            "(backend/frontend/wasp/coding-standards). Slash-prefix "
            "variants included so CC transcript scan picks up invocations."
        ),
    },
    {
        "name": "canvas_render",
        "seed_terms": [
            "canvas-engine",
            "canvas-demo",
            "screenshot-to-code",
            "three-js",
            "three.js",
            "threejs",
            "three-stack",
            "three-js-migrate",
            "react-three-fiber",
            "r3f",
            "drei",
            "anime-js",
            "anime.js",
            "animejs",
            "anime-js-migrate",
            "remotion",
            "webgl",
            "webgpu",
            "shader",
            "raymarch",
            "virtualstudio",
        ],
        "rationale": (
            "Web-rendering pipelines · canvas-engine (anatomy renderer, "
            "Vite sandbox pool) · screenshot-to-code (vision→code) · the "
            "three.js stack (vanilla + R3F + drei + migrate) · anime.js + "
            "migrate · remotion (programmatic video) · virtualstudio + "
            "VirtualStudio-Cinematic-Hero. Generic terms (webgl, webgpu, "
            "shader, raymarch) included for early ChatGPT-era ideation "
            "before named projects existed."
        ),
    },
]


def compute_hits(portfolio_items, seed_terms):
    """Word-boundary match on item.name (case-insensitive).

    A seed matches only if bordered on both sides by non-[a-z0-9_] or string edge.
    This prevents the v1 FP where seed 'stem' matched inside 'operator-system'.

    Returns list of {name, surface, signal_band, matched_terms}.
    """
    seeds_lc = [s.lower() for s in seed_terms]
    compiled = [(s, _compile_seed(s)) for s in seeds_lc]
    hits = []
    for it in portfolio_items:
        nm = it.get("name", "").lower()
        matched = [s for s, rx in compiled if rx.search(nm)]
        if matched:
            hits.append({
                "name": it["name"],
                "surface": it.get("surface"),
                "signal_band": it.get("signal_band"),
                "matched_terms": matched,
            })
    return hits


def main():
    portfolio = json.loads(PORTFOLIO.read_text(encoding="utf-8"))
    items = portfolio["items"]
    total = len(items)

    enriched = []
    seen = set()
    for c in CLUSTERS:
        hits = compute_hits(items, c["seed_terms"])
        for h in hits:
            seen.add(h["name"])
        enriched.append({
            **c,
            "portfolio_hit_count": len(hits),
            "portfolio_hits": hits,
        })

    uncategorized = [
        {"name": it["name"], "surface": it["surface"], "signal_band": it["signal_band"]}
        for it in items
        if it["name"] not in seen
    ]

    out = {
        "phase": "002_KEYWORD_CLUSTERS",
        "sequence": "01_seed_clusters_from_portfolio",
        "generated_at": dt.datetime.utcnow().isoformat(),
        "method": (
            "Cluster names + seed terms hand-derived from portfolio names "
            "and MEMORY.md threads. Hits computed by case-insensitive "
            "substring match on item.name only. Uncategorized list "
            "surfaced for transparency; will fall through Phase 3 cross-"
            "reference matrix unless a cluster claims them in Seq 02 "
            "expansion. HOTL: counts only, no auto-judgement."
        ),
        "portfolio_total": total,
        "categorized_count": len(seen),
        "uncategorized_count": len(uncategorized),
        "clusters": enriched,
        "uncategorized_items": uncategorized,
    }

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"WROTE {OUT}")
    print(f"  portfolio_total={total}")
    print(f"  categorized={len(seen)}  uncategorized={len(uncategorized)}")
    for c in enriched:
        print(f"  {c['name']:24s} hits={c['portfolio_hit_count']}")


if __name__ == "__main__":
    main()
