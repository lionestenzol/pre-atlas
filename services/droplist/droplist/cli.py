"""drop CLI.

    drop "raw messy input here"
    drop --recent 10
    drop --show <drop_id>
    drop --memory-search "query"
    drop --ship "input"        # also emit a Mini Ship packet
"""

from __future__ import annotations

import argparse
import json
import sys

from . import engine, retrieval, storage
from .schema import WorkPacket

# ---- pretty printing -------------------------------------------------------

_C = {
    "head": "\033[1;36m", "key": "\033[0;36m", "warn": "\033[1;33m",
    "block": "\033[0;31m", "ok": "\033[0;32m", "dim": "\033[2m", "off": "\033[0m",
}


def _color(use: bool):
    return _C if use else {k: "" for k in _C}


def print_packet(p: dict, color: bool = True) -> None:
    c = _color(color)
    print(f"\n{c['head']}WORK PACKET  {p['drop_id']}{c['off']}")
    print(f"{c['dim']}{p['created_at']}{c['off']}")
    print(f"{c['key']}input    {c['off']} {p['normalized_input']}")
    print(f"{c['key']}type     {c['off']} {p['type']}    "
          f"{c['key']}domain {c['off']} {p['domain']}    "
          f"{c['key']}conf {c['off']} {p['confidence']}")
    if p.get("entities"):
        print(f"{c['key']}entities {c['off']} {', '.join(p['entities'])}")
    print(f"{c['key']}workflow {c['off']} {p['selected_workflow']}  "
          f"[{p['current_node']} -> {p['next_node']}]")
    print(f"{c['key']}assigned {c['off']} {p['assigned_to']}")
    print(f"{c['ok']}next     {c['off']} {p['next_action']}")
    print(f"{c['key']}stop     {c['off']} {p['stop_condition']}")
    print(f"{c['ok']}allow    {c['off']} {', '.join(p['allowed_actions'])}")
    print(f"{c['block']}block    {c['off']} {', '.join(p['blocked_actions'])}")
    if p.get("needs_human_decision"):
        print(f"{c['warn']}** needs human decision **{c['off']}")
    if p.get("retrieved_context"):
        print(f"{c['key']}context  {c['off']} {len(p['retrieved_context'])} prior packet(s):")
        for ctx in p["retrieved_context"]:
            print(f"  {c['dim']}- [{ctx['relevance']}] {ctx['source']}: {ctx['snippet']}{c['off']}")
    print(f"{c['key']}memory   {c['off']} {p['memory_update']}")
    print(f"{c['key']}status   {c['off']} {p['status']}\n")


def print_ship(s: dict, color: bool = True) -> None:
    c = _color(color)
    print(f"{c['head']}MINI SHIP  {s['ship_id']}{c['off']}  (from {s['source_drop_id']})")
    print(f"{c['key']}type {c['off']} {s['ship_type']}   "
          f"{c['key']}assigned {c['off']} {s['assigned_to']}   "
          f"{c['key']}box {c['off']} {s['time_box']}")
    print(f"{c['ok']}goal {c['off']} {s['goal']}")
    print(f"{c['key']}done {c['off']} {s['definition_of_done']}")
    print(f"{c['key']}test {c['off']} {s['test']}")
    print(f"{c['key']}status {c['off']} {s['status']}\n")


# ---- commands --------------------------------------------------------------


def cmd_drop(text: str, ship: bool, as_json: bool, color: bool) -> int:
    packet, mini = engine.process_drop(text, make_ship=ship)
    errs = packet.validate()
    if as_json:
        out = {"packet": packet.to_dict()}
        if mini:
            out["mini_ship"] = mini.to_dict()
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print_packet(packet.to_dict(), color)
        if mini:
            print_ship(mini.to_dict(), color)
    storage.log_run(
        tool="drop", command=f'drop "{text[:60]}"',
        goal="turn a drop into a Work Packet",
        input_scope=f"1 drop ({len(text)} chars)",
        result_summary=f"{packet.type}/{packet.domain} -> {packet.selected_workflow}"
                       + (f"; mini_ship {mini.ship_id}" if mini else ""),
        important_files=[storage.PACKETS] + ([storage.MINI_SHIPS] if mini else []),
        decision=packet.next_action,
        next_action=packet.next_action,
        memory_update=packet.memory_update,
        status="error" if errs else "success",
    )
    if errs:
        print(f"[WARN] packet validation issues: {errs}", file=sys.stderr)
        return 1
    return 0



def cmd_recent(n: int, color: bool) -> int:
    packets = storage.read_all(storage.PACKETS)[-n:]
    if not packets:
        print("no packets yet.")
        return 0
    c = _color(color)
    for p in packets:
        flag = f" {c['warn']}!{c['off']}" if p.get("needs_human_decision") else ""
        print(f"{c['dim']}{p['created_at']}{c['off']}  {p['drop_id']}  "
              f"[{p['type']}/{p['domain']}]  -> {p['assigned_to']}: {p['next_action']}{flag}")
    return 0


def cmd_show(drop_id: str, color: bool) -> int:
    for p in storage.read_all(storage.PACKETS):
        if p.get("drop_id") == drop_id:
            print_packet(p, color)
            return 0
    print(f"no packet with drop_id {drop_id}", file=sys.stderr)
    return 1


def cmd_memory_search(query: str, color: bool) -> int:
    hits = retrieval.retrieve(query, storage.read_all(storage.PACKETS), k=5)
    if not hits:
        print("no matches.")
        return 0
    c = _color(color)
    for h in hits:
        print(f"{c['ok']}[{h['relevance']}]{c['off']} {h['source']} "
              f"({h.get('type')}/{h.get('domain')}): {h['snippet']}")
    return 0


def _line(p: dict, c: dict) -> str:
    flag = f" {c['warn']}!{c['off']}" if p.get("needs_human_decision") else ""
    return (f"  {p['drop_id']}  [{p['type']}/{p['domain']}]  "
            f"-> {p['assigned_to']}: {p['next_action']}{flag}")


def cmd_morning(color: bool) -> int:
    from . import daily
    b = daily.build_brief()
    c = _color(color)
    print(f"\n{c['head']}MORNING BRIEF{c['off']}  "
          f"{c['dim']}{b['total_open']} open across "
          f"{len(b['by_domain'])} domain(s){c['off']}")
    if b["total_open"] == 0:
        print(f"{c['dim']}  nothing open. clean slate.{c['off']}\n")
        return 0
    print(f"{c['dim']}  {b['by_domain']}{c['off']}")

    print(f"\n{c['ok']}TOP 3 MOVES{c['off']}")
    for p in b["top_3_moves"] or []:
        print(_line(p, c))
    if not b["top_3_moves"]:
        print(f"{c['dim']}  (none actionable){c['off']}")

    if b["urgent_admin"]:
        print(f"\n{c['warn']}URGENT ADMIN{c['off']}")
        for p in b["urgent_admin"]:
            print(_line(p, c))
    if b["waiting_on"]:
        print(f"\n{c['key']}WAITING ON{c['off']}")
        for p in b["waiting_on"]:
            print(_line(p, c))
    if b["decisions_needed"]:
        print(f"\n{c['head']}DECISIONS NEEDED{c['off']}")
        for p in b["decisions_needed"]:
            print(_line(p, c))
    print()
    storage.log_run(
        tool="morning", command="morning",
        goal="daily command brief from unresolved packets",
        input_scope=f"{b['total_open']} open packets",
        result_summary=f"top3={len(b['top_3_moves'])} urgent={len(b['urgent_admin'])} "
                       f"waiting={len(b['waiting_on'])} decisions={len(b['decisions_needed'])}",
        next_action=b["top_3_moves"][0]["next_action"] if b["top_3_moves"] else "",
    )
    return 0


def cmd_review(recent, domain, status, needs_decision, color: bool) -> int:
    from . import review
    r = review.build_review(recent=recent, domain=domain, status=status,
                            needs_decision=needs_decision)
    c = _color(color)

    if r["malformed_lines"]:
        print(f"{c['warn']}[WARN] {len(r['malformed_lines'])} malformed line(s) skipped: "
              f"{r['malformed_lines'][:10]}{c['off']}", file=sys.stderr)

    print(f"\n{c['head']}DROP REVIEW{c['off']}  "
          f"{c['dim']}{r['shown']} of {r['total']} packets"
          f"{'' if r['shown'] == r['total'] else ' (filtered)'}{c['off']}")
    if r["shown"] == 0:
        print(f"{c['dim']}  no packets match. try `drop \"...\"` to create one,"
              f" or relax the filters.{c['off']}\n")
        storage.log_run(tool="drop-review", command="drop-review",
                        goal="surface unresolved work", input_scope="0 matched",
                        result_summary="empty", status="success")
        return 0

    print(f"{c['dim']}  status   {r['by_status']}{c['off']}")
    print(f"{c['dim']}  domain   {r['by_domain']}{c['off']}")
    print(f"{c['dim']}  workflow {r['by_workflow']}{c['off']}")
    print(f"{c['dim']}  assigned {r['by_assigned']}{c['off']}")

    def block(title, items, head):
        if not items:
            return
        print(f"\n{head}{title}{c['off']}")
        for p in items:
            flag = f" {c['warn']}!{c['off']}" if p.get("needs_human_decision") else ""
            print(f"  {p.get('drop_id')}  [{p.get('domain')}/{p.get('status')}]  "
                  f"{p.get('selected_workflow')}  -> {p.get('assigned_to')}{flag}")
            print(f"      {c['ok']}next{c['off']} {p.get('next_action')}")
            print(f"      {c['dim']}stop {p.get('stop_condition')}{c['off']}")

    block("UNRESOLVED (open / routed / waiting)", r["unresolved"], c["head"])
    block("RESOLVED (logged / shipped / archived)", r["resolved"], c["dim"])
    print()

    storage.log_run(
        tool="drop-review", command="drop-review",
        goal="surface unresolved work",
        input_scope=f"{r['total']} packets, {r['shown']} shown",
        result_summary=f"unresolved={len(r['unresolved'])} resolved={len(r['resolved'])} "
                       f"needs_decision={r['needs_decision_count']} malformed={len(r['malformed_lines'])}",
        next_action=r["unresolved"][0]["next_action"] if r["unresolved"] else "",
    )
    return 0


def cmd_inventory(folder: str, do_hash: bool, color: bool) -> int:
    from . import inventory
    c = _color(color)
    try:
        report, packet, inv_path = inventory.run_inventory(folder, do_hash=do_hash)
    except NotADirectoryError as e:
        print(f"not a directory: {e}", file=sys.stderr)
        storage.log_run(tool="inventory", command=f"inventory {folder}",
                        goal="metadata-only file inventory", input_scope=str(folder),
                        result_summary=f"error: not a directory", status="error")
        return 1
    print(f"\n{c['head']}INVENTORY{c['off']}  {report['folder']}")
    print(f"{c['key']}files    {c['off']} {report['file_count']}    "
          f"{c['key']}size {c['off']} {report['total_size_h']}    "
          f"{c['key']}dupes {c['off']} {report['duplicate_candidate_groups']} group(s)"
          f"{'' if report['hashed'] else ' (size+name; --hash to confirm)'}")
    print(f"{c['key']}by ext   {c['off']} " +
          ", ".join(f"{k}:{v}" for k, v in list(report["by_ext"].items())[:8]))
    print(f"{c['key']}written  {c['off']} {inv_path}")
    print(f"{c['dim']}  (contents not read — file_ops DAG, assigned to script){c['off']}")
    print_packet(packet.to_dict(), color)
    storage.log_run(
        tool="inventory", command=f"inventory {folder}" + (" --hash" if do_hash else ""),
        goal="metadata-only file inventory",
        input_scope=f"{report['file_count']} files, {report['total_size_h']}",
        result_summary=f"{report['duplicate_candidate_groups']} dup groups; packet {packet.drop_id}",
        important_files=[inv_path, storage.PACKETS],
        decision="contents not read; metadata only",
        next_action=packet.next_action,
        memory_update=packet.memory_update,
    )
    return 0


def cmd_brief(color: bool) -> int:
    from . import command_brief
    b = command_brief.build_brief()
    c = _color(color)
    t = b["totals"]
    print(f"\n{c['head']}DAILY COMMAND BRIEF{c['off']}  {c['dim']}{b['day']}  "
          f"({t['dags']} graphs: {t['ready']} ready, {t['blocked']} blocked, "
          f"{t['waiting']} waiting){c['off']}")

    def show(title, rows, head, withtool=False):
        print(f"\n{head}{title}{c['off']}")
        if not rows:
            print(f"{c['dim']}  —{c['off']}")
            return
        for i, r in enumerate(rows, 1):
            tool = f" {c['dim']}<{r['tool']}>{c['off']}" if withtool and r.get("tool") else ""
            proj = f" {c['dim']}({r['project']}){c['off']}" if r.get("project") else ""
            print(f"  {i}. {r['title']} — {r['domain']}{proj}{tool}  "
                  f"{c['dim']}[{r['dag']}/{r['node']} p{r['priority']}]{c['off']}")

    show("READY NOW", b["ready"], c["ok"], withtool=True)
    show("BLOCKED", b["blocked"], c["block"])
    show("WAITING", b["waiting"], c["key"])
    show("OVERDUE", b["overdue"], c["warn"])

    print(f"\n{c['key']}RECURRING{c['off']}")
    if b["recurring"]:
        for r in b["recurring"]:
            print(f"  - {r['title']} ({r['recurrence']}, {r['domain']}) "
                  f"{c['dim']}last: {r['last_materialized'] or 'never'}{c['off']}")
    else:
        print(f"{c['dim']}  —{c['off']}")

    print(f"\n{c['block']}DO NOT REOPEN{c['off']}")
    if b["do_not_reopen"]:
        for ref, meta in b["do_not_reopen"].items():
            print(f"  - {ref}  {c['dim']}({meta['reason']}){c['off']}")
    else:
        print(f"{c['dim']}  —{c['off']}")

    nb = b["next_best"]
    print(f"\n{c['head']}NEXT BEST NODE{c['off']}  "
          + (f"{nb['title']} — {nb['domain']} [{nb['dag']}/{nb['node']}]" if nb
             else "— nothing ready") + "\n")

    storage.log_run(tool="brief", command="brief", goal="daily command brief",
                    result_summary=f"ready={t['ready']} blocked={t['blocked']} "
                                    f"waiting={t['waiting']} dags={t['dags']}",
                    next_action=nb["title"] if nb else "")
    return 0


def cmd_watch(color: bool) -> int:
    from . import watcher
    r = watcher.tick()
    c = _color(color)
    print(f"\n{c['head']}WATCH TICK{c['off']}  {c['dim']}{r['at']}{c['off']}")
    print(f"  recurring materialized: {len(r['recurring_materialized'])}")
    for m in r["recurring_materialized"]:
        print(f"    {c['ok']}+{c['off']} {m['title']}  {c['dim']}{m['dag_id']}{c['off']}")
    print(f"  stale (>stale_after): {len(r['stale'])}")
    for s in r["stale"]:
        print(f"    {c['warn']}!{c['off']} {s['title']} {c['dim']}({s['age_hours']}h, {s['dag']}/{s['node']}){c['off']}")
    print(f"  blocked resurfaced: {len(r['blocked_resurfaced'])}   "
          f"escalations: {len(r['escalations'])}\n")
    storage.log_run(tool="watch", command="watch", goal="watcher tick",
                    result_summary=f"materialized={len(r['recurring_materialized'])} "
                                    f"stale={len(r['stale'])} escalations={len(r['escalations'])}")
    return 0


def cmd_entities(color: bool) -> int:
    from . import entities
    c = _color(color)
    ents = entities.list_all()
    print(f"\n{c['head']}ENTITIES{c['off']}  {c['dim']}{len(ents)} tracked{c['off']}")
    for e in ents:
        print(f"  {c['key']}{e['entity_id']}{c['off']} ({e['type']})  "
              f"{len(e['related_dags'])} dag(s)  {c['dim']}last: "
              f"{e.get('last_observation','')[:50]}{c['off']}")
    print()
    return 0


def cmd_recurring_add(spec: str, color: bool) -> int:
    """spec format: 'title | domain | recurrence'"""
    from . import state
    parts = [s.strip() for s in spec.split("|")]
    title = parts[0]
    domain = parts[1] if len(parts) > 1 else "general"
    rec = parts[2] if len(parts) > 2 else "daily"
    rn = state.add_recurring(title, domain, recurrence=rec)
    print(f"added recurring {rn['id']}: {title} ({rec}, {domain})")
    return 0


def cmd_graph(text: str, as_json: bool, color: bool) -> int:
    from . import graph_engine
    c = _color(color)
    trace = graph_engine.run_graph(text)
    if as_json:
        print(json.dumps(trace, indent=2, ensure_ascii=False))
        storage.log_run(tool="graph", command=f'graph "{text[:50]}"',
                        goal="run recursive DAG loop",
                        result_summary=f"{trace['dag_id']} {trace['state']['dag_status']}")
        return 0

    p = trace["packet"]
    s = trace["state"]
    print(f"\n{c['head']}GRAPH RUN  {trace['dag_id']}{c['off']}  "
          f"{c['dim']}(from {p['drop_id']}){c['off']}")
    print(f"{c['key']}1 what  {c['off']} {p['type']}/{p['domain']}  — {p['normalized_input'][:64]}")
    print(f"{c['key']}  goal  {c['off']} {trace['goal']}")

    # 2 nodes + 3 dependencies (with tool type)
    print(f"\n{c['key']}2/3 nodes, tools & dependencies{c['off']}")
    dag = storage.load_dag(trace["dag_id"])
    for n in dag["nodes"]:
        dep = f"  needs {','.join(n['depends_on'])}" if n["depends_on"] else ""
        kind = n["tool_type"] or "reasoning"
        print(f"  {n['id']}  {c['key']}<{kind}>{c['off']} [{n['agent']}] {n['title']}{c['dim']}{dep}{c['off']}")
        if n["done_condition"]:
            print(f"      {c['dim']}done when: {n['done_condition']}{c['off']}")

    # 4 what can run now (initial)
    print(f"\n{c['key']}4 ready now{c['off']}  {', '.join(trace['initial_ready'])}")

    # 5/6/7 cycles
    for rec in trace["cycles"]:
        print(f"\n{c['head']}cycle {rec['cycle']}{c['off']}")
        for d in rec["dispatched"]:
            via = f"tool:{d['tool']}" if d["tool"] != "-" else d["agent"]
            print(f"  {c['ok']}5 run    {c['off']} {d['node']} {c['dim']}<{d['kind']}>{c['off']} via {via}")
            print(f"  {c['key']}6 result {c['off']} {d['result'][:88]}")
        for r in rec["reviews"]:
            tag = c['ok'] if r['status'] == 'pass' else (
                c['warn'] if r['status'] == 'retry' else c['block'])
            print(f"  {tag}  review {c['off']} {r['node']}: {r['status']} -> {r['mark']} "
                  f"{c['dim']}({r['reason']}){c['off']}")
        for u in rec["updates"]:
            print(f"  {c['warn']}7 graph  {c['off']} {u}")

    # tool receipts (evidence)
    if trace["tool_runs"]:
        print(f"\n{c['key']}tool receipts (evidence){c['off']}")
        for tr in trace["tool_runs"]:
            print(f"  {tr['tool_run_id']}  {tr['tool_type']}.{tr['action']}  "
                  f"{c['ok'] if tr['status']=='success' else c['block']}{tr['status']}{c['off']}")

    # 8 final state
    print(f"\n{c['head']}8 final state{c['off']}  {s['dag_status']}  "
          f"{c['dim']}({s['tool_actions']} tool action(s)){c['off']}")
    print(f"  done {s['done']}  blocked {s['blocked']}  failed {s['failed']}  waiting {s['waiting']}")
    if s["blocked"]:
        print(f"  {c['warn']}awaiting you: {', '.join(s['blocked'])}{c['off']}")
    print(f"  next ready: {s['next_ready'] or '— none (graph settled)'}   "
          f"recursive updates this run: {s['recursive_updates']}\n")

    storage.log_run(
        tool="graph", command=f'graph "{text[:50]}"',
        goal="run recursive DAG loop", input_scope=f"{s['total_nodes']} nodes",
        result_summary=f"{trace['dag_id']} -> {s['dag_status']}; "
                       f"done={len(s['done'])} recursive_updates={s['recursive_updates']}",
        important_files=[f"dags/{trace['dag_id']}.json", storage.AGENT_RUNS],
        decision=trace["goal"], next_action=s["next_ready"] or "settled",
        status="success" if trace["dag_valid"] else "error",
    )
    return 0


def cmd_ship_from(drop_id: str, color: bool) -> int:
    ship = engine.ship_from(drop_id)
    if ship is None:
        print(f"no packet with drop_id {drop_id}", file=sys.stderr)
        storage.log_run(tool="ship-from", command=f"ship-from {drop_id}",
                        goal="convert packet to Mini Ship", input_scope=drop_id,
                        result_summary="packet not found", status="error")
        return 1
    print_ship(ship.to_dict(), color)
    storage.log_run(
        tool="ship-from", command=f"ship-from {drop_id}",
        goal="convert packet to Mini Ship", input_scope=drop_id,
        result_summary=f"{ship.ship_type} ship {ship.ship_id} ({ship.status})",
        important_files=[storage.MINI_SHIPS],
        decision=ship.goal, next_action=ship.definition_of_done,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="drop", description="DropList Packet Engine CLI")
    p.add_argument("input", nargs="?", help="raw messy input to drop")
    p.add_argument("--ship", action="store_true", help="also emit a Mini Ship packet")
    p.add_argument("--recent", type=int, metavar="N", help="show the last N packets")
    p.add_argument("--show", metavar="DROP_ID", help="show one packet by id")
    p.add_argument("--memory-search", metavar="QUERY", help="keyword search prior packets")
    p.add_argument("--morning", action="store_true", help="print the daily command brief")
    p.add_argument("--review", action="store_true", help="surface unresolved work (drop-review)")
    p.add_argument("--domain", metavar="DOMAIN", help="(with --review) filter by domain")
    p.add_argument("--status", metavar="STATUS", help="(with --review) filter by status")
    p.add_argument("--needs-decision", action="store_true",
                   help="(with --review) only packets needing a human decision")
    p.add_argument("--inventory", metavar="FOLDER", help="metadata-only inventory of a folder")
    p.add_argument("--hash", action="store_true", help="(with --inventory) sample-hash to confirm dupes")
    p.add_argument("--ship-from", metavar="DROP_ID", help="convert a stored packet into a Mini Ship")
    p.add_argument("--graph", metavar="INPUT", help="run the recursive DAG loop on a drop")
    p.add_argument("--brief", action="store_true", help="daily command brief across all graphs")
    p.add_argument("--watch", action="store_true", help="run a watcher tick (recurring/stale/escalation)")
    p.add_argument("--entities", action="store_true", help="list tracked entities")
    p.add_argument("--recurring-add", metavar="SPEC",
                   help="add a recurring node: 'title | domain | recurrence'")
    p.add_argument("--json", action="store_true", help="emit raw JSON")
    p.add_argument("--no-color", action="store_true", help="disable ANSI color")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    color = not args.no_color and sys.stdout.isatty()

    if args.recent is not None:
        return cmd_recent(args.recent, color)
    if args.show:
        return cmd_show(args.show, color)
    if args.memory_search:
        return cmd_memory_search(args.memory_search, color)
    if args.morning:
        return cmd_morning(color)
    if args.review:
        return cmd_review(args.recent, args.domain, args.status,
                          args.needs_decision, color)
    if args.inventory:
        return cmd_inventory(args.inventory, args.hash, color)
    if args.ship_from:
        return cmd_ship_from(args.ship_from, color)
    if args.graph:
        return cmd_graph(args.graph, args.json, color)
    if args.brief:
        return cmd_brief(color)
    if args.watch:
        return cmd_watch(color)
    if args.entities:
        return cmd_entities(color)
    if args.recurring_add:
        return cmd_recurring_add(args.recurring_add, color)
    if args.input:
        return cmd_drop(args.input, args.ship, args.json, color)

    build_parser().print_help()
    return 0


def brief_main(argv: list[str] | None = None) -> int:
    return cmd_brief(sys.stdout.isatty())


def watch_main(argv: list[str] | None = None) -> int:
    return cmd_watch(sys.stdout.isatty())


def graph_main(argv: list[str] | None = None) -> int:
    """Entry point for the `graph "<input>"` command."""
    pa = argparse.ArgumentParser(prog="graph")
    pa.add_argument("input")
    pa.add_argument("--json", action="store_true")
    pa.add_argument("--no-color", action="store_true")
    a = pa.parse_args(argv)
    color = not a.no_color and sys.stdout.isatty()
    return cmd_graph(a.input, a.json, color)


def review_main(argv: list[str] | None = None) -> int:
    """Entry point for the `drop-review [filters]` command."""
    pa = argparse.ArgumentParser(prog="drop-review")
    pa.add_argument("--recent", type=int)
    pa.add_argument("--domain")
    pa.add_argument("--status")
    pa.add_argument("--needs-decision", action="store_true", dest="needs_decision")
    pa.add_argument("--no-color", action="store_true")
    a = pa.parse_args(argv)
    color = not a.no_color and sys.stdout.isatty()
    return cmd_review(a.recent, a.domain, a.status, a.needs_decision, color)


def morning_main(argv: list[str] | None = None) -> int:
    """Entry point for the `morning` command."""
    return cmd_morning(sys.stdout.isatty())


def inventory_main(argv: list[str] | None = None) -> int:
    """Entry point for the `inventory <folder> [--hash]` command."""
    pa = argparse.ArgumentParser(prog="inventory")
    pa.add_argument("folder")
    pa.add_argument("--hash", action="store_true")
    a = pa.parse_args(argv)
    return cmd_inventory(a.folder, a.hash, sys.stdout.isatty())


def shipfrom_main(argv: list[str] | None = None) -> int:
    """Entry point for the `ship-from <drop_id>` command."""
    pa = argparse.ArgumentParser(prog="ship-from")
    pa.add_argument("drop_id")
    a = pa.parse_args(argv)
    return cmd_ship_from(a.drop_id, sys.stdout.isatty())


if __name__ == "__main__":
    raise SystemExit(main())
