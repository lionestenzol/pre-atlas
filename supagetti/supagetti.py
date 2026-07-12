#!/usr/bin/env python3
"""SupaGetti v0 CLI entrypoint."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import analyzer, case_manager, governor, intake, ledger, loader, reporter, scanner
from core.models import PhaseStatus

CAST_PHASES = [
    ("scan", lambda case_id: scanner.run_scan(case_id)),
    ("analyze", lambda case_id: analyzer.run_analyze(case_id)),
    ("govern", lambda case_id: governor.run_govern(case_id)),
    ("report", lambda case_id: reporter.run_report(case_id)),
    ("ledger", lambda case_id: ledger.run_ledger(case_id)),
]


def _print_status(result: PhaseStatus) -> None:
    if result.status == "ok":
        print(f"[{result.phase}] ok")
    else:
        print(f"[{result.phase}] FAILED: {result.reason}", file=sys.stderr)


def cmd_new_case(args: argparse.Namespace) -> int:
    case_dir = case_manager.create_case(args.name)
    print(f"Created case: {case_dir.name}")
    print(f"  intake.json: {case_dir / 'intake.json'}")
    print(f"  source/:     {case_dir / 'source'}")
    return 0


def cmd_intake(args: argparse.Namespace) -> int:
    result = intake.run_intake(args.case_id)
    _print_status(result)
    return 0 if result.status == "ok" else 1


def cmd_load(args: argparse.Namespace) -> int:
    if args.folder:
        result = loader.load_folder(args.case_id, args.folder)
    elif args.zip:
        result = loader.load_zip(args.case_id, args.zip)
    elif args.repo:
        result = loader.load_repo(args.case_id, args.repo)
    else:
        print("load requires one of --folder, --zip, --repo", file=sys.stderr)
        return 1
    _print_status(result)
    return 0 if result.status == "ok" else 1


def cmd_scan(args: argparse.Namespace) -> int:
    result = scanner.run_scan(args.case_id)
    _print_status(result)
    return 0 if result.status == "ok" else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    result = analyzer.run_analyze(args.case_id)
    _print_status(result)
    return 0 if result.status == "ok" else 1


def cmd_govern(args: argparse.Namespace) -> int:
    result = governor.run_govern(args.case_id)
    _print_status(result)
    return 0 if result.status == "ok" else 1


def cmd_report(args: argparse.Namespace) -> int:
    result = reporter.run_report(args.case_id)
    _print_status(result)
    return 0 if result.status == "ok" else 1


def cmd_ledger(args: argparse.Namespace) -> int:
    result = ledger.run_ledger(args.case_id)
    _print_status(result)
    return 0 if result.status == "ok" else 1


def cmd_cast(args: argparse.Namespace) -> int:
    """Phase 9 — orchestrator: scan -> analyze -> govern -> report -> ledger."""
    try:
        case_manager.resolve_case_id(args.case_id)
    except case_manager.CaseNotFoundError as exc:
        print(f"[cast] FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"=== cast {args.case_id} ===")
    for phase_name, run_fn in CAST_PHASES:
        result = run_fn(args.case_id)
        _print_status(result)
        if result.status == "failed":
            print(f"\ncast halted at phase '{phase_name}'.", file=sys.stderr)
            print(f"Required fix: {result.reason}", file=sys.stderr)
            return 1
    print("\ncast complete: all phases ok.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="supagetti.py", description="SupaGetti v0")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new-case", help="Create a new case")
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_new_case)

    p = sub.add_parser("intake", help="Run interactive intake for a case")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_intake)

    p = sub.add_parser("load", help="Load source into a case")
    p.add_argument("case_id")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--folder")
    g.add_argument("--zip")
    g.add_argument("--repo")
    p.set_defaults(func=cmd_load)

    p = sub.add_parser("scan", help="Run the deterministic scanner")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("analyze", help="Run the LLM analyzer")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("govern", help="Run the governor review")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_govern)

    p = sub.add_parser("report", help="Generate the report")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("ledger", help="Generate the ledger entry")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_ledger)

    p = sub.add_parser("cast", help="Run scan -> analyze -> govern -> report -> ledger")
    p.add_argument("case_id")
    p.set_defaults(func=cmd_cast)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
