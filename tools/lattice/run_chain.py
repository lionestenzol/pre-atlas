#!/usr/bin/env python3
"""Run a live LangGraph chain of skill invocations (Seq 2 + Seq 3 + Seq 5 + Seq 7).

Wires skill_nodes.invoke_skill (Seq 2 -- claude-agent-sdk -> seam.v1 Receipt) into
graph.build_chain_graph (Seq 3 -- durable StateGraph, @task-wrapped nodes,
AsyncSqliteSaver checkpointing) so a chain of real agentic skill calls is
crash-resumable: kill this process mid-chain, re-run with the same --thread-id,
and completed steps do not re-invoke the SDK. After a successful run, feeds the
same tool-outcomes.jsonl ledger combo.py scores (Seq 5, opt-in via SEAM_LEDGER=1
-- see ledger_feed.py), so lattice-driven runs teach the bandit, not just
interactive/seam usage.

    python run_chain.py --thread-id t1 code-recon "locate where run_id is threaded"
    python run_chain.py --thread-id t1 code-recon "prompt A" weapon "prompt B"   # 2-step chain
    python run_chain.py --thread-id t1 --resume                                  # resume after a crash
    SEAM_LEDGER=1 python run_chain.py --thread-id t1 code-recon "..."            # also feed the ledger

Checkpoints persist to lattice_runs.sqlite (next to this file) by default -- a
real process restart reconnects to the same file, same as
test_resume_survives_a_fresh_saver_instance_against_the_same_file proves
hermetically in services/atlas-map-api/tests/test_lattice_graph.py.

Seq 7 (Supervisor) adds opt-in registration with delta-kernel's work queue
(supervisor.py) -- LangGraph itself has no auto-resume, so something external
must call ainvoke(None, config) after a real OS-level crash. --supervised
registers this run as a delta-kernel `system` job before it starts; if the
process dies without completing, the job's timeout_at lapses and
WorkController.checkTimeouts() retries it, and governance_daemon.ts's
resumeLatticeJob re-launches this exact command with --resume --job-id. --demo
runs a 3-step zero-cost synthetic chain (same checkpointing, no LLM call) so
the kill/resume/supervise loop can be proven without spending real budget on
every cycle:

    python run_chain.py --thread-id t7 --demo --supervised --demo-delay 3
    # kill the process after "demo-a" logs, then wait for the daemon's
    # next work_queue tick (or POST /api/work/... to force it) --
    # governance_daemon.ts resumes it without a human touching it.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from graph import StepFn, build_chain_graph  # noqa: E402
from skill_nodes import DEFAULT_MAX_BUDGET_USD, DEFAULT_MAX_TURNS, invoke_skill  # noqa: E402
from schemas import SKILL_SCHEMAS  # noqa: E402
from ledger_feed import append_ledger  # noqa: E402
from demo_steps import demo_step  # noqa: E402
import supervisor  # noqa: E402

DEFAULT_DB_PATH = str(_HERE / "lattice_runs.sqlite")


def _pair_args(raw: list[str]) -> list[tuple[str, str]]:
    if len(raw) % 2 != 0:
        raise SystemExit(f"expected skill/prompt pairs, got an odd count of args: {raw!r}")
    return [(raw[i], raw[i + 1]) for i in range(0, len(raw), 2)]


def _node_names(pairs: list[tuple[str, str]]) -> list[str]:
    """Disambiguate node names when the same skill appears more than once in the chain."""
    seen: dict[str, int] = {}
    names = []
    for skill, _ in pairs:
        seen[skill] = seen.get(skill, 0) + 1
        names.append(skill if seen[skill] == 1 else f"{skill}_{seen[skill]}")
    return names


def _make_step_fn(skill: str, prompt: str, *, max_turns: int, max_budget_usd: float):
    async def _fn() -> dict[str, Any]:
        receipt = await invoke_skill(skill, prompt, max_turns=max_turns, max_budget_usd=max_budget_usd)
        return receipt.model_dump()

    return _fn


async def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="run_chain", description=__doc__.splitlines()[0])
    p.add_argument("--thread-id", required=True, help="LangGraph thread_id -- reuse it to resume")
    p.add_argument("--db", default=DEFAULT_DB_PATH, help=f"checkpoint sqlite file (default: {DEFAULT_DB_PATH})")
    p.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    p.add_argument("--max-budget", type=float, default=DEFAULT_MAX_BUDGET_USD)
    p.add_argument("--resume", action="store_true",
                    help="resume an interrupted --thread-id -- pass the SAME skill/prompt pairs "
                         "as the original run, so the graph shape matches; completed steps are "
                         "skipped, LangGraph doesn't re-invoke their @task")
    p.add_argument("--json", action="store_true")
    p.add_argument("--demo", action="store_true",
                    help="run a 3-step zero-cost synthetic chain instead of real skill pairs "
                         "(Seq 7 -- proves crash/resume + delta-kernel supervision without "
                         "spending real budget on every kill/resume cycle)")
    p.add_argument("--demo-delay", type=float, default=0.8,
                    help="seconds each demo step sleeps -- raise this to give yourself time to "
                         "kill the process mid-chain when live-testing the supervisor")
    p.add_argument("--supervised", action="store_true",
                    help="register this run with delta-kernel's work queue (Seq 7) so a killed "
                         "run can be resumed by checkTimeouts() without human action")
    p.add_argument("--job-id", default=None,
                    help="reuse an existing delta-kernel work-queue job_id instead of "
                         "registering a new one -- passed by governance_daemon.ts when it "
                         "resumes a retried job, so completion reports against the SAME job")
    p.add_argument("--delta-kernel-url", default=supervisor.DEFAULT_BASE_URL)
    p.add_argument("--job-timeout-ms", type=int, default=120_000,
                    help="delta-kernel job timeout_ms -- how long before an unresponsive run "
                         "is considered dead and retried by checkTimeouts()")
    p.add_argument("pairs", nargs="*", help="skill prompt [skill prompt ...] (ignored with --demo)")
    args = p.parse_args(argv)

    if not args.demo and not args.pairs:
        raise SystemExit("provide at least one 'skill prompt' pair (same pairs again if --resume-ing), "
                          "or pass --demo")

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    config = {"configurable": {"thread_id": args.thread_id}}

    if args.demo:
        names = ["demo-a", "demo-b", "demo-c"]
        pairs: list[tuple[str, str]] | None = None
        steps = {n: StepFn(name=n, fn=demo_step(n, delay=args.demo_delay)) for n in names}
    else:
        pairs = _pair_args(args.pairs)
        names = _node_names(pairs)
        unknown = [skill for skill, _ in pairs if skill not in SKILL_SCHEMAS]
        if unknown:
            raise SystemExit(f"unknown skill(s) {unknown} -- known: {sorted(SKILL_SCHEMAS)}")
        steps = {
            name: StepFn(
                name=name,
                fn=_make_step_fn(skill, prompt, max_turns=args.max_turns, max_budget_usd=args.max_budget),
            )
            for name, (skill, prompt) in zip(names, pairs)
        }

    job_id = args.job_id
    supervised = args.supervised or job_id is not None
    if supervised and job_id is None:
        job_id = await asyncio.to_thread(
            supervisor.register_job, args.delta_kernel_url,
            thread_id=args.thread_id, pairs=pairs, db=args.db,
            max_turns=args.max_turns, max_budget_usd=args.max_budget,
            timeout_ms=args.job_timeout_ms, demo=args.demo,
        )
        if job_id is None:
            print("lattice: delta-kernel unreachable or job not approved -- continuing unsupervised",
                  file=sys.stderr)

    try:
        async with AsyncSqliteSaver.from_conn_string(args.db) as saver:
            graph = build_chain_graph(steps, order=names, checkpointer=saver)
            initial_input = None if args.resume else {"receipts": []}
            result = await graph.ainvoke(initial_input, config, durability="sync")
    except Exception as e:
        if supervised and job_id:
            await asyncio.to_thread(
                supervisor.complete_job, args.delta_kernel_url, job_id,
                outcome="failed", error=str(e),
            )
        raise

    receipts = result["receipts"]
    n_ledger_rows = append_ledger(receipts, args.thread_id)
    if n_ledger_rows:
        print(f"lattice: fed {n_ledger_rows} row(s) to the tool-outcomes ledger", file=sys.stderr)

    all_ok = all(r["status"] == "ok" for r in receipts)
    if supervised and job_id:
        completed = await asyncio.to_thread(
            supervisor.complete_job, args.delta_kernel_url, job_id,
            outcome="completed" if all_ok else "failed",
        )
        if completed:
            print(f"lattice: reported completion to delta-kernel job {job_id}", file=sys.stderr)

    if args.json:
        print(json.dumps(receipts, indent=2, sort_keys=True))
    else:
        for r in receipts:
            line = f"{r['tool']}: {r['status']}"
            if r["sha256"]:
                line += f" sha256={r['sha256'][:12]}..."
            print(line)
            if r["status"] == "error":
                print(f"  error: {r['error']}")
    return 0 if all_ok else 1


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
