"""
Atlas CLI — Single entry point for the Atlas governance stack.

Usage:
    python atlas_cli.py daily     Run full daily loop (refresh + brief)
    python atlas_cli.py weekly    Run full weekly loop (daily + audit + packet)
    python atlas_cli.py backlog   Run idea pipeline + backlog maintenance
    python atlas_cli.py briefs    Generate briefs only (no refresh)
    python atlas_cli.py status    Show system status and file freshness
"""

import sys
from atlas_agent import AtlasAgent


COMMANDS = {
    "daily":   "run_daily",
    "weekly":  "run_weekly",
    "backlog": "maintain_backlog",
    "briefs":  "generate_briefs_only",
    "status":  "status",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.strip())
        print("\nCommands:")
        print("  daily    Full daily loop: refresh state -> governor brief")
        print("  weekly   Full weekly loop: daily + audit + governor packet")
        print("  backlog  Re-run idea pipeline + conversation classifier")
        print("  briefs   Generate daily + weekly briefs from current state")
        print("  status   Show system status and file freshness")
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    agent = AtlasAgent()
    method = getattr(agent, COMMANDS[cmd])
    method()


if __name__ == "__main__":
    main()
