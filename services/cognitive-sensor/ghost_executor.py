#!/usr/bin/env python3
"""
GHOST EXECUTOR -- Autonomous First-Move Agent
=============================================
Reads Genesis tree outputs and produces actionable directives.
Designed to run on a cron cycle and integrate with Atlas governance.

What it does:
  1. Reads genesis_scoreboard.json, genesis_cross_links.json, genesis_convergences.json
  2. For ACTIVE_MATURE branches: generates execution directives
  3. For cross-links: generates collision hypotheses (recombinant ideas)
  4. For convergences: generates high-conviction action items
  5. Outputs a daily directive file that governor_daily.py consumes

Respects Atlas mode gates: reads current mode from governance_state.json
and only suggests actions the current mode allows.

Outputs:
  - genesis_output/ghost_directives.json
  - genesis_output/ghost_collisions.json
  - genesis_output/ghost_brief.md

Usage:
  python ghost_executor.py  # uses defaults relative to script dir
  python ghost_executor.py --genesis-dir ./genesis_output --atlas-state ./governance_state.json
"""

import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BASE = Path(__file__).parent.resolve()

MAX_DIRECTIVES_PER_CYCLE = 5
MAX_COLLISIONS_PER_CYCLE = 10
ACTIVE_THRESHOLD = 0.45       # Minimum maturity to generate directives
COLLISION_MIN_SIM = 0.42      # Minimum cross-link sim for collision generation

# Atlas mode gates -- ghost executor respects these
MODE_GATES: dict[str, dict[str, list[str]]] = {
    "RECOVER":     {"allow": []},
    "CLOSURE":     {"allow": ["close_loop", "archive"]},
    "MAINTENANCE": {"allow": ["close_loop", "archive", "research"]},
    "BUILD":       {"allow": ["close_loop", "archive", "research",
                              "create", "execute"]},
    "COMPOUND":    {"allow": ["close_loop", "archive", "research",
                              "create", "execute", "ship"]},
    "SCALE":       {"allow": ["close_loop", "archive", "research",
                              "create", "execute", "ship", "delegate"]},
}

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------

def load_genesis(genesis_dir: str) -> dict[str, Any]:
    """Load all Genesis outputs."""
    data: dict[str, Any] = {}
    files = {
        'tree': 'genesis_tree.json',
        'scoreboard': 'genesis_scoreboard.json',
        'cross_links': 'genesis_cross_links.json',
        'convergences': 'genesis_convergences.json',
    }

    for key, filename in files.items():
        path = os.path.join(genesis_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data[key] = json.load(f)
            print(f"  Loaded {filename}")
        else:
            print(f"  Missing {filename}")
            data[key] = [] if key != 'tree' else {}

    return data


def load_atlas_state(state_path: str | None) -> dict[str, Any]:
    """Load current Atlas governance state."""
    if state_path and os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'mode': 'BUILD',
        'open_loops': 0,
        'closure_ratio': 100.0,
        'build_allowed': True
    }

# ---------------------------------------------------------------------------
# DIRECTIVE GENERATION
# ---------------------------------------------------------------------------

def _check_energy_gate() -> tuple[bool, int]:
    """Check if energy gate blocks high-load directive generation."""
    life_path = BASE / "life_signals.json"
    if not life_path.exists():
        return False, 50
    life = json.loads(life_path.read_text(encoding="utf-8"))
    energy = life.get("energy", {})
    level = energy.get("energy_level", 50)
    burnout = energy.get("burnout_risk", False)
    gated = level < 30 or burnout
    return gated, level


def generate_directives(
    scoreboard: list[dict],
    tree: dict[str, dict],
    atlas_state: dict[str, Any],
) -> list[dict]:
    """Generate execution directives from scored branches.
    Respects Atlas mode gates and energy constraints."""
    current_mode = atlas_state.get('mode', 'BUILD')
    allowed_actions = MODE_GATES.get(current_mode, {}).get('allow', [])

    # Energy gate: block EXECUTE/INVEST directives when depleted
    energy_gated, energy_level = _check_energy_gate()
    if energy_gated:
        allowed_actions = [a for a in allowed_actions if a in ('close_loop', 'archive', 'research')]
        print(f"  [ghost_executor] Energy gate active (level={energy_level}) — restricted to lightweight actions")
    directives: list[dict] = []

    for branch in scoreboard:
        if branch['maturity_score'] < ACTIVE_THRESHOLD:
            continue

        domain_id = str(branch['domain_id'])
        domain_data = tree.get(domain_id, {})
        label = domain_data.get('label', 'unknown')

        if branch['status'] == 'ACTIVE_MATURE':
            if 'execute' in allowed_actions:
                directive = {
                    'type': 'EXECUTE',
                    'priority': branch['maturity_score'],
                    'domain': label,
                    'domain_id': domain_id,
                    'rationale': (
                        f"Branch '{label}' has "
                        f"{branch['conversation_count']} conversations, "
                        f"{branch['total_user_words']:,} words invested, "
                        f"and is actively being developed. "
                        f"Maturity: {branch['maturity_score']:.3f}. "
                        f"Ready to produce a shippable asset."
                    ),
                    'suggested_action': (
                        f"Ship something from the '{label}' domain."),
                    'sub_branches': branch['sub_branch_count'],
                    'blocked': False
                }
            else:
                directive = {
                    'type': 'QUEUED',
                    'priority': branch['maturity_score'],
                    'domain': label,
                    'domain_id': domain_id,
                    'rationale': (
                        f"Branch '{label}' is ready for execution but "
                        f"current mode ({current_mode}) blocks creation. "
                        f"Will activate when mode allows."
                    ),
                    'suggested_action': (
                        f"Mode gate: waiting for BUILD/COMPOUND/SCALE."),
                    'blocked': True,
                    'blocked_by': current_mode
                }

        elif branch['status'] == 'DORMANT_MATURE':
            if 'research' in allowed_actions:
                directive = {
                    'type': 'RESURRECT',
                    'priority': branch['maturity_score'] * 0.8,
                    'domain': label,
                    'domain_id': domain_id,
                    'rationale': (
                        f"Branch '{label}' has deep investment "
                        f"({branch['total_user_words']:,} words) but "
                        f"has gone inactive. Recency: "
                        f"{branch['recency']:.2f}. Significant sunk "
                        f"cost -- evaluate if conditions changed."
                    ),
                    'suggested_action': (
                        f"Spend 30min reviewing the '{label}' domain. "
                        f"Has the market, your skills, or your interest "
                        f"changed?"
                    ),
                    'blocked': False
                }
            else:
                continue

        elif branch['status'] == 'GROWING':
            if 'create' in allowed_actions:
                directive = {
                    'type': 'INVEST',
                    'priority': branch['maturity_score'] * 0.7,
                    'domain': label,
                    'domain_id': domain_id,
                    'rationale': (
                        f"Branch '{label}' is actively growing "
                        f"({branch['conversation_count']} convos) "
                        f"but needs more depth before it's actionable. "
                        f"Recency: {branch['recency']:.2f}."
                    ),
                    'suggested_action': (
                        f"Deepen the '{label}' domain -- fill gaps, "
                        f"prototype, or formalize what you've explored."
                    ),
                    'blocked': False
                }
            else:
                continue
        else:
            continue

        directives.append(directive)

    directives.sort(key=lambda x: -x['priority'])
    return directives[:MAX_DIRECTIVES_PER_CYCLE]

# ---------------------------------------------------------------------------
# COLLISION GENERATION
# ---------------------------------------------------------------------------

def generate_collisions(
    cross_links: list[dict],
    tree: dict[str, dict],
) -> list[dict]:
    """Generate recombinant ideas from cross-domain connections."""
    collisions: list[dict] = []

    for link in cross_links:
        if link['similarity'] < COLLISION_MIN_SIM:
            continue

        domain_a = tree.get(str(link['domain_a']), {})
        domain_b = tree.get(str(link['domain_b']), {})
        label_a = domain_a.get('label', '?')
        label_b = domain_b.get('label', '?')

        collision = {
            'domains': [label_a, label_b],
            'similarity': link['similarity'],
            'link_type': link.get('type', 'domain_bridge'),
            'hypothesis': (
                f"Cross-pollination opportunity: '{label_a}' and "
                f"'{label_b}' share semantic structure "
                f"(sim: {link['similarity']}). Patterns from one "
                f"may transfer to the other."
            ),
            'members_a': domain_a.get('member_count', 0),
            'members_b': domain_b.get('member_count', 0),
            'collision_score': round(
                link['similarity'] *
                min(domain_a.get('member_count', 1), 50) / 50 *
                min(domain_b.get('member_count', 1), 50) / 50,
                4
            )
        }
        collisions.append(collision)

    collisions.sort(key=lambda x: -x['collision_score'])
    return collisions[:MAX_COLLISIONS_PER_CYCLE]

# ---------------------------------------------------------------------------
# CONVERGENCE DIRECTIVES
# ---------------------------------------------------------------------------

def generate_convergence_directives(
    convergences: list[dict],
    tree: dict[str, dict],
) -> list[dict]:
    """High-conviction items from convergence detection."""
    conv_directives: list[dict] = []

    for c in convergences[:5]:
        domain_a = tree.get(str(c['domain_a']), {})
        domain_b = tree.get(str(c['domain_b']), {})
        label_a = domain_a.get('label', '?')
        label_b = domain_b.get('label', '?')

        conv_directives.append({
            'type': 'CONVERGENCE',
            'domains': [label_a, label_b],
            'score': c['convergence_score'],
            'evidence_count': c['members_a'] + c['members_b'],
            'rationale': (
                f"Independent thinking in '{label_a}' "
                f"({c['members_a']} convos) and '{label_b}' "
                f"({c['members_b']} convos) converged to the same "
                f"semantic region (score: {c['convergence_score']}). "
                f"High-conviction signal -- you arrived here from "
                f"multiple angles without planning to."
            ),
            'suggested_action': (
                f"Investigate the overlap between '{label_a}' and "
                f"'{label_b}'. What conclusion did both paths lead to? "
                f"That's likely a core belief or insight worth "
                f"formalizing and acting on."
            )
        })

    return conv_directives

# ---------------------------------------------------------------------------
# BRIEF GENERATION
# ---------------------------------------------------------------------------

def generate_brief(
    directives: list[dict],
    collisions: list[dict],
    convergence_dirs: list[dict],
    atlas_state: dict[str, Any],
    output_dir: str,
) -> None:
    """Generate the daily ghost brief -- one page, actionable."""
    now = datetime.now()
    mode = atlas_state.get('mode', 'BUILD')
    open_loops = atlas_state.get('open_loops', '?')

    # Handle both flat and nested governance_state formats
    closure = atlas_state.get('closure', {})
    if closure:
        closure_ratio = closure.get('ratio', '?')
    else:
        closure_ratio = atlas_state.get('closure_ratio', '?')

    lines = [
        "# GHOST BRIEF",
        "",
        f"*{now.strftime('%A, %B %d, %Y -- %I:%M %p')}*",
        f"*Atlas Mode: {mode} | Open Loops: {open_loops} "
        f"| Closure Ratio: {closure_ratio}%*",
        "",
        "---",
        "",
    ]

    active_directives = [d for d in directives if not d.get('blocked')]
    blocked_directives = [d for d in directives if d.get('blocked')]

    if active_directives:
        top = active_directives[0]
        lines += [
            "## #1 MOVE",
            "",
            f"**{top['type']}**: {top['domain']}",
            "",
            f"{top['rationale']}",
            "",
            f"-> **{top['suggested_action']}**",
            "",
        ]

        if len(active_directives) > 1:
            lines.append("## ALSO ON DECK")
            lines.append("")
            for d in active_directives[1:]:
                lines.append(
                    f"- **{d['type']}** -- {d['domain']}: "
                    f"{d['suggested_action']}")
            lines.append("")
    else:
        allowed = MODE_GATES.get(mode, {}).get('allow', [])
        lines += [
            "## NO ACTIVE DIRECTIVES",
            "",
            f"Current mode ({mode}) is gating execution. ",
            f"Focus on what's allowed: {', '.join(allowed)}",
            "",
        ]

    if blocked_directives:
        lines.append("## QUEUED (mode-gated)")
        lines.append("")
        for d in blocked_directives:
            lines.append(
                f"- {d['domain']} -- waiting for "
                f"{d.get('blocked_by', '?')} to clear")
        lines.append("")

    if collisions:
        lines += [
            "---", "",
            "## COLLISION CANDIDATES", "",
            "Cross-domain patterns that could produce something new:", "",
        ]
        for c in collisions[:5]:
            lines.append(
                f"- **{c['domains'][0]}** x **{c['domains'][1]}** "
                f"(score: {c['collision_score']})")
        lines.append("")

    if convergence_dirs:
        lines += [
            "---", "",
            "## HIGH-CONVICTION CONVERGENCES", "",
            "You arrived at these points from multiple independent angles:",
            "",
        ]
        for c in convergence_dirs:
            lines.append(
                f"- **{c['domains'][0]}** <-> **{c['domains'][1]}** "
                f"({c['evidence_count']} convos converging, "
                f"score: {c['score']})")
            lines.append(f"  -> {c['suggested_action']}")
        lines.append("")

    lines += [
        "---", "",
        f"*Generated by Ghost Executor at {now.strftime('%H:%M')}. "
        f"Fed into Atlas governor_daily for governance integration.*"
    ]

    brief_path = os.path.join(output_dir, 'ghost_brief.md')
    with open(brief_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"  Brief: {brief_path}")

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Ghost Executor -- Autonomous Directive Agent')
    parser.add_argument(
        '--genesis-dir', default=str(BASE / 'genesis_output'),
        help='Path to Genesis output directory')
    parser.add_argument(
        '--atlas-state', default=str(BASE / 'governance_state.json'),
        help='Path to Atlas governance_state.json')
    parser.add_argument(
        '--output', default=None,
        help='Output directory (defaults to genesis-dir)')
    args = parser.parse_args()

    output_dir = args.output or args.genesis_dir
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  GHOST EXECUTOR -- Autonomous First-Move Agent")
    print("=" * 60)

    print("\n[1/5] Loading Genesis data...")
    genesis = load_genesis(args.genesis_dir)

    print("\n[2/5] Loading Atlas state...")
    atlas_state = load_atlas_state(args.atlas_state)
    print(f"  Mode: {atlas_state.get('mode', '?')}")

    print("\n[3/5] Generating directives...")
    directives = generate_directives(
        genesis['scoreboard'], genesis['tree'], atlas_state)
    print(f"  {len(directives)} directives generated")

    print("\n[4/5] Generating collisions...")
    collisions = generate_collisions(
        genesis['cross_links'], genesis['tree'])
    convergence_dirs = generate_convergence_directives(
        genesis['convergences'], genesis['tree'])
    print(f"  {len(collisions)} collisions, "
          f"{len(convergence_dirs)} convergence directives")

    print("\n[5/5] Writing outputs...")

    directives_path = os.path.join(output_dir, 'ghost_directives.json')
    with open(directives_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'atlas_mode': atlas_state.get('mode', 'UNKNOWN'),
            'directives': directives,
            'convergence_directives': convergence_dirs
        }, f, indent=2)
    print(f"  Directives: {directives_path}")

    collisions_path = os.path.join(output_dir, 'ghost_collisions.json')
    with open(collisions_path, 'w', encoding='utf-8') as f:
        json.dump(collisions, f, indent=2)
    print(f"  Collisions: {collisions_path}")

    generate_brief(
        directives, collisions, convergence_dirs, atlas_state, output_dir)

    print("\n" + "=" * 60)
    print("  GHOST EXECUTOR COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()
