import argparse
import json
import sys
from .client import FestClient, FestError


def main() -> int:
    ap = argparse.ArgumentParser(prog="fest-py", description="Python wrapper over fest CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list")
    sp.add_argument("--status", default=None)
    sp.add_argument("--all", action="store_true")

    sp = sub.add_parser("progress")
    sp.add_argument("festival")

    sp = sub.add_parser("next")
    sp.add_argument("festival")

    sub.add_parser("status")

    sp = sub.add_parser("promote")
    sp.add_argument("festival")
    sp.add_argument("--dungeon", default=None)
    sp.add_argument("--force", action="store_true")

    sp = sub.add_parser("task-complete")
    sp.add_argument("festival")
    sp.add_argument("task_id")

    args = ap.parse_args()
    c = FestClient()

    try:
        if args.cmd == "list":
            out = [f.model_dump() for f in c.list(args.status, all_=args.all)]
        elif args.cmd == "progress":
            out = c.progress(args.festival).model_dump()
        elif args.cmd == "next":
            out = c.next(args.festival).model_dump()
        elif args.cmd == "status":
            out = c.status()
        elif args.cmd == "promote":
            out = c.promote(args.festival, args.dungeon, force=args.force)
        elif args.cmd == "task-complete":
            out = c.task_complete(args.festival, args.task_id)
        else:
            return 2
    except FestError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(out if isinstance(out, str) else json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
