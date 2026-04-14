"""Quick smoke test for the compound feedback loop.

Runs the compound loop directly without needing delta-kernel or NATS.
Uses real brain/ files from cognitive-sensor if available.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mosaic.config import config
from mosaic.clients.cognitive_client import CognitiveClient


class MockDeltaClient:
    """Stub delta client that returns empty unified state."""
    async def get_unified_state(self):
        return {"error": "delta-kernel not running (mock)", "derived": {}}


async def main():
    cognitive = CognitiveClient(config.cognitive_sensor_dir)
    delta = MockDeltaClient()

    print(f"Sensor dir: {config.cognitive_sensor_dir}")
    print(f"Exists: {config.cognitive_sensor_dir.exists()}")
    print()

    # Check what brain files exist
    brain_dir = config.cognitive_sensor_dir / "cycleboard" / "brain"
    if brain_dir.exists():
        files = sorted(brain_dir.glob("*.json"))
        print(f"Brain files ({len(files)}):")
        for f in files:
            size = f.stat().st_size
            print(f"  {f.name} ({size} bytes)")
    else:
        print(f"Brain dir not found: {brain_dir}")
    print()

    # Run compound loop
    from mosaic.workflows.compound_loop import run_compound_loop

    print("Running compound loop...")
    print("=" * 60)
    result = await run_compound_loop(cognitive, delta, publisher=None, openclaw=None)
    print("=" * 60)
    print()

    # Show results
    print(f"Compound Score: {result.get('compound_score', '?')}/100")
    print()

    domain_scores = result.get("domain_scores", {})
    if domain_scores:
        print("Domain Scores:")
        for domain, score in sorted(domain_scores.items()):
            filled = round(score / 10)
            bar = "#" * filled + "-" * (10 - filled)
            print(f"  {domain:10s} [{bar}] {score:.0f}")
    print()

    loops = result.get("loops", {})
    fired = {k: v for k, v in loops.items() if v.get("fired")}
    not_fired = {k: v for k, v in loops.items() if not v.get("fired")}

    if fired:
        print(f"Fired loops ({len(fired)}):")
        for name, lr in fired.items():
            print(f"  {name}: {lr.get('output_summary', '')}")

    if not_fired:
        print(f"\nInactive loops ({len(not_fired)}):")
        for name, lr in not_fired.items():
            print(f"  {name}: {lr.get('input_summary', '')}")
    print()

    constraints = result.get("active_constraints", [])
    if constraints:
        print(f"Active Constraints ({len(constraints)}):")
        for c in constraints:
            print(f"  [{c.get('severity', '?')}] {c.get('source_domain')} -> {c.get('target_domain')}: {c.get('constraint')}")
    print()

    signal_updates = result.get("signal_updates", {})
    if signal_updates:
        print("Signal Updates (pushed back):")
        print(f"  {json.dumps(signal_updates, indent=2)}")
    print()

    # Check if compound_state.json was written
    out_path = brain_dir / "compound_state.json"
    if out_path.exists():
        print(f"compound_state.json written: {out_path} ({out_path.stat().st_size} bytes)")
    else:
        print("compound_state.json NOT written")

    # Print brief (ASCII-safe)
    brief = result.get("compound_brief", "")
    if brief:
        print()
        print("=" * 60)
        # Replace unicode chars with ASCII for Windows console
        safe_brief = brief.encode("ascii", errors="replace").decode("ascii")
        print(safe_brief)


if __name__ == "__main__":
    asyncio.run(main())
