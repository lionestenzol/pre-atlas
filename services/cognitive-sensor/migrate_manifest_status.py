"""
migrate_manifest_status — backfill `status` on every existing
harvest/<id>_<slug>/manifest.json.

Default behavior: set status="HARVESTED" on any manifest that lacks one.
Does not clobber existing status values.

Usage:
  python migrate_manifest_status.py            # dry run, prints what would change
  python migrate_manifest_status.py --apply    # write changes
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).parent.resolve()
HARVEST_ROOT = BASE / "harvest"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (otherwise dry-run)")
    args = ap.parse_args()

    if not HARVEST_ROOT.exists():
        print(f"no harvest folder at {HARVEST_ROOT}")
        return 0

    total = 0
    updated = 0
    already = 0
    for sub in sorted(HARVEST_ROOT.iterdir()):
        if not sub.is_dir():
            continue
        manifest_path = sub / "manifest.json"
        if not manifest_path.exists():
            continue
        total += 1
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  [skip malformed] {manifest_path}")
            continue

        if data.get("status"):
            already += 1
            continue

        data["status"] = "HARVESTED"
        print(f"  [{'apply' if args.apply else 'dry '}] {sub.name} -> HARVESTED")
        if args.apply:
            manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            updated += 1

    print(f"\ntotal manifests: {total}  already-tagged: {already}  "
          f"{'updated' if args.apply else 'would update'}: {updated if args.apply else total - already}")
    if not args.apply and total - already > 0:
        print("re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
