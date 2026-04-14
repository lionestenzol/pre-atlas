"""
Governance Config API — Export governance configuration to JSON.

Reads from atlas_config.py (single source of truth) and writes
governance_config.json so TypeScript services can access the same rules.
"""

import json
from pathlib import Path
from atlas_config import (
    NORTH_STAR, TARGETS, ROUTING, ACTIVE_LANES,
    IDEAS_RESERVOIR_RULES, DAILY_BRIEF_TEMPLATE, WEEKLY_PACKET_TEMPLATE,
    AutonomyLevel,
)

BASE = Path(__file__).parent.resolve()


def main():
    config = {
        "schema_version": "1.0.0",
        "north_star": NORTH_STAR,
        "targets": TARGETS,
        "routing": ROUTING,
        "active_lanes": [
            {
                "id": lane["id"],
                "name": lane["name"],
                "type": lane["type"],
                "status": lane["status"],
                "ship_criteria": lane["ship_criteria"],
                "deadline_weeks": lane["deadline_weeks"],
            }
            for lane in ACTIVE_LANES
        ],
        "reservoir_rules": IDEAS_RESERVOIR_RULES,
        "brief_template": DAILY_BRIEF_TEMPLATE,
        "weekly_template": WEEKLY_PACKET_TEMPLATE,
    }

    out_path = BASE / "governance_config.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"Wrote {out_path.name} ({len(json.dumps(config))} bytes)")


if __name__ == "__main__":
    main()
