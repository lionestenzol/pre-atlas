"""
cli.py — argparse glue for `atl fuzz` subcommands.

Wired into atlas_triage_cli.py's build_parser via cmd_fuzz.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fuzz.generator import generate_corpus
from fuzz.shapes import SHAPE_REGISTRY

_DEFAULT_OUT = Path(__file__).resolve().parent.parent / "fuzz-corpus"


def _cmd_gen(args: argparse.Namespace) -> int:
    out_base = Path(args.out).resolve() if args.out else _DEFAULT_OUT
    try:
        run_dir = generate_corpus(
            seed=args.seed,
            count=args.count,
            out_base=out_base,
            run_id=args.run_id,
        )
    except ValueError as e:
        print(f"[fuzz gen] {e}", file=sys.stderr)
        return 2

    print(f"[fuzz gen] wrote {args.count} files to {run_dir}")
    print(f"[fuzz gen] next: open {run_dir / 'f000.html'} in Chrome "
          f"with the anatomy extension, then auto-label.")
    return 0


def _cmd_list_shapes(args: argparse.Namespace) -> int:
    import random
    probe = random.Random(0)
    rows = []
    for name, fn in SHAPE_REGISTRY.items():
        frag = fn(probe, "__list__")
        rows.append((name, frag.should_fire, frag.labels_produced, frag.slop))

    print(f"{'shape':<28} {'fires':<6} {'labels':<7} {'slop':<5}")
    print("-" * 50)
    for name, fires, produced, slop in rows:
        mark = "YES" if fires else "no"
        print(f"{name:<28} {mark:<6} {produced:<7} {slop:<5}")
    print(f"\ntotal: {len(rows)} shapes "
          f"({sum(1 for r in rows if r[1])} firing / "
          f"{sum(1 for r in rows if not r[1])} filter)")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    # Lazy import — playwright is an opt-in dep.
    from fuzz.runner import (
        PlaywrightMissing,
        latest_corpus_dir,
        run as run_corpus,
    )

    if args.corpus:
        corpus_dir = Path(args.corpus).resolve()
    else:
        corpus_dir = latest_corpus_dir(_DEFAULT_OUT)
        if corpus_dir is None:
            print(f"[fuzz run] no corpus found under {_DEFAULT_OUT}. "
                  f"Run `atl fuzz gen` first.", file=sys.stderr)
            return 2

    out_path = (
        Path(args.out).resolve() if args.out
        else (corpus_dir / "report.json")
    )
    try:
        report = run_corpus(
            corpus_dir=corpus_dir,
            out_path=out_path,
            limit=args.limit,
            timeout_seconds=float(args.timeout),
            headless=args.headless,
        )
    except PlaywrightMissing as e:
        print(f"[fuzz run] {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"[fuzz run] {e}", file=sys.stderr)
        return 2

    totals = report["totals"]
    return 0 if (totals["fail"] == 0 and totals["error"] == 0) else 1


def _cmd_pull_or_vendor(args: argparse.Namespace, mode: str) -> int:
    from fuzz.pull import _load_url_list, pull_corpus

    try:
        urls = _load_url_list(args.urls or [], args.from_file)
    except (ValueError, FileNotFoundError) as e:
        print(f"[fuzz {('pull' if mode == 'S' else 'vendor')}] {e}", file=sys.stderr)
        return 2
    if not urls:
        print(f"[fuzz {('pull' if mode == 'S' else 'vendor')}] "
              f"no urls. pass urls or --from FILE.", file=sys.stderr)
        return 2

    out_base = Path(args.out).resolve() if args.out else _DEFAULT_OUT
    run_dir, results = pull_corpus(
        urls=urls,
        out_base=out_base,
        mode=mode,
        run_id=args.run_id,
        timeout_s=float(args.timeout),
        start_index=int(args.start_index),
    )
    failed = sum(1 for r in results if not r.ok)
    return 0 if failed == 0 else 1


def cmd_fuzz(args: argparse.Namespace, extra: list[str]) -> int:
    """Dispatch `atl fuzz <subcmd>`. Called from atlas_triage_cli.py."""
    sub = getattr(args, "fuzz_cmd", None)
    if sub == "gen":
        return _cmd_gen(args)
    if sub == "list-shapes":
        return _cmd_list_shapes(args)
    if sub == "run":
        return _cmd_run(args)
    if sub == "pull":
        return _cmd_pull_or_vendor(args, mode="S")
    if sub == "vendor":
        return _cmd_pull_or_vendor(args, mode="M")
    print(f"[fuzz] unknown subcommand: {sub!r}", file=sys.stderr)
    return 2


def _add_pull_args(p: argparse.ArgumentParser, default_timeout: float) -> None:
    p.add_argument("urls", nargs="*", help="URL(s) to pull")
    p.add_argument("--from", dest="from_file", default=None,
                   help="newline-delimited URL list (# comments ok)")
    p.add_argument("--out", default=None,
                   help="base output directory (default: ./fuzz-corpus)")
    p.add_argument("--run-id", default=None,
                   help="override run dir name (default: <utc>-pull<mode>)")
    p.add_argument("--timeout", type=float, default=default_timeout,
                   help=f"per-url timeout seconds (default: {default_timeout:.0f})")
    p.add_argument("--start-index", type=int, default=0,
                   help="numbering offset (default: 0 -> r000, r001, ...)")
    p.set_defaults(func=cmd_fuzz)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Attach `fuzz` to the parent `atl` parser."""
    fuzz_p = subparsers.add_parser(
        "fuzz", help="generate/run fuzz corpus for the anatomy extension"
    )
    fuzz_sub = fuzz_p.add_subparsers(dest="fuzz_cmd", required=True)

    gen = fuzz_sub.add_parser("gen", help="generate a deterministic HTML corpus")
    gen.add_argument("--seed", type=int, default=42,
                     help="RNG seed (default: 42)")
    gen.add_argument("--count", type=int, default=50,
                     help="number of HTML files to generate (default: 50)")
    gen.add_argument("--out", type=str, default=None,
                     help="base output directory (default: ./fuzz-corpus)")
    gen.add_argument("--run-id", type=str, default=None,
                     help="override the run directory name "
                          "(default: <utc>-seed<N>)")
    gen.set_defaults(func=cmd_fuzz)

    ls = fuzz_sub.add_parser("list-shapes", help="dump the shape registry")
    ls.set_defaults(func=cmd_fuzz)

    rn = fuzz_sub.add_parser(
        "run", help="run the corpus through Chrome+anatomy ext, write report",
    )
    rn.add_argument("--corpus", type=str, default=None,
                    help="corpus run directory (default: most recent under "
                         "./fuzz-corpus/)")
    rn.add_argument("--out", type=str, default=None,
                    help="report path (default: <corpus>/report.json)")
    rn.add_argument("--limit", type=int, default=None,
                    help="run only the first N files (smoke testing)")
    rn.add_argument("--timeout", type=float, default=30.0,
                    help="per-file timeout in seconds (default: 30)")
    rn.add_argument("--headless", action="store_true",
                    help="use --headless=new (default: headed window)")
    rn.set_defaults(func=cmd_fuzz)

    pl = fuzz_sub.add_parser(
        "pull", help="S-mode: pull URLs into self-contained .html via single-file-cli",
    )
    _add_pull_args(pl, default_timeout=120.0)

    vd = fuzz_sub.add_parser(
        "vendor", help="M-mode: pull URLs into multi-file dirs via sitepull",
    )
    _add_pull_args(vd, default_timeout=180.0)
