"""Acceptance harness. Runs 20 real drops and checks every spec criterion.

    python test_drops.py            # run all, print summary
    python test_drops.py --verbose  # also print each packet

Uses an isolated data dir so it never pollutes real logs.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

# isolate storage before importing the package
_TMP = tempfile.mkdtemp(prefix="droplist_test_")
os.environ["DROPLIST_DATA"] = _TMP

from droplist import engine, storage  # noqa: E402
from droplist.schema import TYPES, DOMAINS  # noqa: E402

# (drop_text, expected_type_or_None, expected_domain_or_None)
DROPS = [
    ("Spark burned tokens on 14k Drive files because it tried to read too much before metadata indexing.",
     "problem", "file_ops"),
    ("The watermelon vine on the BSFL rabbit bedding mound is growing aggressively again.",
     "log", "animal_property"),
    ("DropList should be treated as an intake agent, not a task app.",
     "decision", "build_product"),
    ("Add a --recent flag to the drop CLI that prints the last N packets.",
     "task", "build_product"),
    ("The packet completion sometimes returns an empty next_action when classifier confidence is low.",
     "problem", "build_product"),
    ("Clean up the duplicate project folders in my Drive.",
     "task", "file_ops"),
    ("What if Atlas exposed a vector search endpoint that DropList queries before routing.",
     "idea", "build_product"),
    ("One of the goats is limping and won't put weight on its back left leg.",
     "warning", "animal_property"),
    ("Fed the chickens and topped off the rabbit water, all normal.",
     "log", "animal_property"),
    ("Got the truck insurance renewal notice, due end of month, $612.",
     "asset", "money_admin"),
    ("Need to call the vet and schedule the spring shots.",
     "task", "money_admin"),
    ("Still waiting on the receipt from the feed store for taxes.",
     "follow_up", "money_admin"),
    ("Give me my morning brief.",
     "task", "daily_command"),
    ("The electric bill is way higher than usual this month.",
     "problem", "money_admin"),
    ("Note: USDA Section 502 has income caps that vary by county.",
     "reference", "general"),
    ("Mini Ship could auto-generate a CLAUDE.md from the work packet.",
     "idea", "build_product"),
    ("Move the BSFL bins into shade before the heat wave.",
     "task", "animal_property"),
    ("Use a plain Python dispatcher for v1, defer LangGraph until sub-DAGs need parallelism.",
     "decision", "build_product"),
    ("Here's a folder of old Strudel compositions to inventory.",
     "asset", "file_ops"),
    ("The drop command crashes if the data directory doesn't exist yet.",
     "problem", "build_product"),
]


def run(verbose: bool = False) -> int:
    from droplist.cli import print_packet

    results = []
    classification_correct = 0
    classification_checked = 0

    for text, exp_type, exp_domain in DROPS:
        packet, _ = engine.process_drop(text)
        errs = packet.validate()
        results.append((packet, errs))
        if verbose:
            print_packet(packet.to_dict(), color=False)

        if exp_type is not None:
            classification_checked += 1
            ok = packet.type == exp_type and packet.domain == exp_domain
            classification_correct += int(ok)
            mark = "OK " if ok else "XX "
            print(f"{mark}[{packet.type}/{packet.domain}]"
                  f"{'' if ok else f' (expected {exp_type}/{exp_domain})'}  {text[:60]}")

    print("\n" + "=" * 64)
    print("ACCEPTANCE TEST RESULTS")
    print("=" * 64)

    # 1 & 7: 20 drops processed, each prints a valid packet
    n = len(results)
    valid = [p for p, e in results if not e]
    print(f"1/7. processed {n} drops; {len(valid)}/{n} valid Work Packets")

    # 2: appended to packets.jsonl
    saved = storage.read_all(storage.PACKETS)
    print(f"2.   packets.jsonl now holds {len(saved)} records (expected {n})")

    # 3: classifier returns allowed enums
    enum_ok = all(p.type in TYPES and p.domain in DOMAINS for p, _ in results)
    print(f"3.   all type/domain values within allowed enums: {enum_ok}")

    # 4: required fields present
    fields_ok = all(
        p.selected_workflow and p.next_action and p.stop_condition
        and isinstance(p.allowed_actions, list) and p.allowed_actions
        and isinstance(p.blocked_actions, list) and p.blocked_actions
        and p.memory_update and p.status
        for p, _ in results
    )
    print(f"4.   every packet has workflow/next/stop/allow/block/memory/status: {fields_ok}")

    # 5: caching — re-run drop #1, classifier should not re-run (cache hit logged)
    calls_before = len(storage.read_all(storage.LLM_CALLS))
    engine.process_drop(DROPS[0][0])
    calls_after = storage.read_all(storage.LLM_CALLS)
    new_calls = calls_after[calls_before:]
    cache_hit = any(c.get("model") == "cache" for c in new_calls)
    print(f"5.   re-running an identical drop hit the classification cache: {cache_hit}")

    # 6: at least 20 real drops
    print(f"6.   >= 20 real drops processed: {n >= 20}")

    # classification accuracy (informational, not a hard gate)
    acc = classification_correct / classification_checked if classification_checked else 0
    print(f"\nclassification accuracy on labeled drops: "
          f"{classification_correct}/{classification_checked} ({acc:.0%})")

    all_pass = (
        len(valid) == n and len(saved) == n and enum_ok and fields_ok
        and cache_hit and n >= 20
    )
    print("\n" + ("ALL ACCEPTANCE CRITERIA PASS" if all_pass else "SOME CRITERIA FAILED"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv
    try:
        code = run(verbose)
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    raise SystemExit(code)
