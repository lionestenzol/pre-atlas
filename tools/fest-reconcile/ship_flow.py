#!/usr/bin/env python3
"""
Phase 4 / Seq 01: ship_flow_per_item

For each portfolio item with signal_band == 'strong', emit a channel-flow record
joining ChatGPT (idea), Claude Code (build), and filesystem (ship/last-active).

Read-only inputs (no raw-corpus touch):
  - portfolio_evidence.json (band=strong filter)
  - festival_out/clusters_final.json (portfolio_hits + seed_terms)
  - festival_out/chatgpt_temporal.json
  - festival_out/cc_temporal.json
  - festival_out/fs_temporal.json

Output:
  - festival_out/ship_flow.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _match import _compile_seed  # word-boundary regex

OUT_DIR = os.path.join(HERE, "festival_out")

# FP_RISK_CLUSTERS is now loaded dynamically from clusters_final.json's
# validation.substring_warnings (see main()). v1 hardcoded
# {"audio_music", "productivity_skills"}.
PARALLEL_WINDOW_DAYS = 7


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_date(s):
    if not s:
        return None
    try:
        if "T" in s:
            s2 = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s2)
        else:
            dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def days_between(later, earlier):
    if later is None or earlier is None:
        return None
    return round((later - earlier).total_seconds() / 86400, 2)


def find_idea_chatgpt(item_name, seed_terms, chatgpt_items):
    # Word-boundary regex for the item name (matches whole-name only).
    name_rx = _compile_seed(item_name.lower())
    name_hits = []
    for it in chatgpt_items:
        title = (it.get("title") or "").lower()
        if name_rx.search(title):
            d = parse_date(it.get("first_date"))
            if d is not None:
                name_hits.append((d, it))

    if name_hits:
        name_hits.sort(key=lambda x: x[0])
        d, hit = name_hits[0]
        return {
            "idea_at": hit.get("first_date"),
            "idea_via": "name_match",
            "convo_id": hit.get("convo_id"),
            "title": hit.get("title"),
        }

    seed_lc = [s.lower() for s in seed_terms]
    compiled = [(s, _compile_seed(s)) for s in seed_lc]
    seed_hits = []
    for it in chatgpt_items:
        title = (it.get("title") or "").lower()
        matched = next((s for s, rx in compiled if rx.search(title)), None)
        if matched:
            d = parse_date(it.get("first_date"))
            if d is not None:
                seed_hits.append((d, it, matched))

    if seed_hits:
        seed_hits.sort(key=lambda x: x[0])
        d, hit, matched = seed_hits[0]
        return {
            "idea_at": hit.get("first_date"),
            "idea_via": "cluster_fallback",
            "convo_id": hit.get("convo_id"),
            "title": hit.get("title"),
            "matched_seed_term": matched,
        }

    return None


def find_build_cc(item_name, cc_items):
    name_rx = _compile_seed(item_name.lower())
    hits = []
    for it in cc_items:
        msg = (it.get("first_user_msg") or "").lower()
        if name_rx.search(msg):
            d = parse_date(it.get("first_ts"))
            if d is not None:
                hits.append((d, it))

    if not hits:
        return None
    hits.sort(key=lambda x: x[0])
    d, hit = hits[0]
    preview = (hit.get("first_user_msg") or "")[:180]
    return {
        "build_at": hit.get("first_ts"),
        "session_id": hit.get("session_id"),
        "first_user_msg_preview": preview,
    }


def find_ship_fs(item_name, surface, fs_items):
    for it in fs_items:
        if it.get("name") == item_name and it.get("surface") == surface:
            return {
                "ship_at": it.get("ctime"),
                "last_active_at": it.get("mtime"),
                "path": it.get("path"),
                "fs_error": it.get("error"),
            }
    return None


def classify_flow(idea_d, build_d):
    """5 buckets per spec: talk_leads | build_leads | parallel | no_talk | no_build.
    no_talk subsumes the case where build is also missing.
    """
    if idea_d is None:
        return "no_talk", None
    if build_d is None:
        return "no_build", None
    lag_ib = days_between(build_d, idea_d)
    if abs(lag_ib) <= PARALLEL_WINDOW_DAYS:
        return "parallel", lag_ib
    if lag_ib > 0:
        return "talk_leads", lag_ib
    return "build_leads", lag_ib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clusters", default=os.path.join(OUT_DIR, "clusters_final.json"))
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "ship_flow.json"))
    args = ap.parse_args()

    portfolio = load(os.path.join(HERE, "portfolio_evidence.json"))
    clusters = load(args.clusters)
    chatgpt = load(os.path.join(OUT_DIR, "chatgpt_temporal.json"))
    cc = load(os.path.join(OUT_DIR, "cc_temporal.json"))
    fs = load(os.path.join(OUT_DIR, "fs_temporal.json"))

    chatgpt_items = chatgpt["items"]
    cc_items = cc["items"]
    fs_items = fs["items"]

    # Dynamic FP_RISK_CLUSTERS: any cluster with at least one substring_warning
    # surfaced in Phase 2 validation is considered FP-prone for cluster_fallback ideas.
    FP_RISK_CLUSTERS = {
        cl["name"]
        for cl in clusters["clusters"]
        if cl.get("validation", {}).get("substring_warnings")
    }

    name_to_clusters = {}
    cluster_seed_terms = {}
    for cl in clusters["clusters"]:
        cluster_seed_terms[cl["name"]] = cl["seed_terms"]
        for hit in cl["portfolio_hits"]:
            lst = name_to_clusters.setdefault(hit["name"], [])
            if cl["name"] not in lst:
                lst.append(cl["name"])

    strong_items = [it for it in portfolio["items"] if it.get("signal_band") == "strong"]

    flows = []
    pattern_counts = {}
    caveat_count = 0

    for item in strong_items:
        name = item["name"]
        surface = item["surface"]
        item_clusters = name_to_clusters.get(name, [])

        seed_terms = []
        seen = set()
        for cn in item_clusters:
            for t in cluster_seed_terms.get(cn, []):
                if t not in seen:
                    seen.add(t)
                    seed_terms.append(t)

        idea = find_idea_chatgpt(name, seed_terms, chatgpt_items)
        build = find_build_cc(name, cc_items)
        ship = find_ship_fs(name, surface, fs_items)

        idea_d = parse_date(idea["idea_at"]) if idea else None
        build_d = parse_date(build["build_at"]) if build else None
        ship_d = parse_date(ship["ship_at"]) if (ship and ship.get("ship_at")) else None

        pattern, lag_ib = classify_flow(idea_d, build_d)
        lag_bs = days_between(ship_d, build_d) if (ship_d and build_d) else None
        lag_is = days_between(ship_d, idea_d) if (ship_d and idea_d) else None

        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        idea_prov = None
        if idea:
            idea_prov = {"convo_id": idea["convo_id"], "title": idea["title"]}
            if idea.get("idea_via") == "cluster_fallback":
                idea_prov["matched_seed_term"] = idea["matched_seed_term"]

        build_prov = None
        if build:
            build_prov = {
                "session_id": build["session_id"],
                "first_user_msg_preview": build["first_user_msg_preview"],
            }

        ship_prov = None
        if ship:
            ship_prov = {"path": ship.get("path")}
            if ship.get("fs_error"):
                ship_prov["fs_error"] = ship["fs_error"]

        record = {
            "name": name,
            "surface": surface,
            "clusters": item_clusters,
            "idea_at": idea["idea_at"] if idea else None,
            "idea_via": idea["idea_via"] if idea else None,
            "idea_provenance": idea_prov,
            "build_at": build["build_at"] if build else None,
            "build_provenance": build_prov,
            "ship_at": ship.get("ship_at") if ship else None,
            "last_active_at": ship.get("last_active_at") if ship else None,
            "ship_provenance": ship_prov,
            "lag_idea_to_build_days": lag_ib,
            "lag_build_to_ship_days": lag_bs,
            "lag_idea_to_ship_days": lag_is,
            "flow_pattern": pattern,
        }

        if idea and idea.get("idea_via") == "cluster_fallback":
            risk_hit = next((c for c in item_clusters if c in FP_RISK_CLUSTERS), None)
            if risk_hit:
                record["caveat"] = "substring_fp_risk"
                record["caveat_reason"] = (
                    f"idea_at via cluster_fallback in '{risk_hit}', which has "
                    "known substring false positives from Phase 2 (stem/system/ecosystem "
                    "or fest/manifesting/lifestyle)"
                )
                caveat_count += 1

        flows.append(record)

    out = {
        "phase": "004_CHANNEL_FLOW_ANALYSIS",
        "sequence": "01_ship_flow_per_item",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "Per strong-band portfolio item, derive: idea_at = earliest ChatGPT convo "
            "first_date whose title contains item name (case-insensitive substring), "
            "fallback to cluster seed-term match; build_at = earliest CC session first_ts "
            "whose first_user_msg contains item name; ship_at = fs_temporal ctime joined "
            "by (name, surface); last_active_at = fs_temporal mtime. Lags in days. "
            f"flow_pattern deterministic: parallel if |lag_idea_to_build| <= {PARALLEL_WINDOW_DAYS}d, "
            "else talk_leads / build_leads by sign. no_talk if no ChatGPT hit at all, "
            "no_build if ChatGPT hit but no CC hit. Caveat 'substring_fp_risk' attached "
            "to cluster_fallback ideas in audio_music or productivity_skills."
        ),
        "input_strong_count": len(strong_items),
        "output_record_count": len(flows),
        "flow_pattern_counts": pattern_counts,
        "caveat_substring_fp_risk_count": caveat_count,
        "fp_risk_clusters_carried_forward": sorted(FP_RISK_CLUSTERS),
        "parallel_window_days": PARALLEL_WINDOW_DAYS,
        "items": flows,
    }

    out_path = args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"wrote {out_path}")
    print(f"strong items: {len(strong_items)}")
    print(f"records: {len(flows)}")
    print(f"caveats (substring_fp_risk): {caveat_count}")
    print(f"flow_pattern counts: {json.dumps(pattern_counts, indent=2)}")
    print()
    print("=== spot-check rows (>=5) ===")
    spot_checks = []
    for f in flows:
        if f.get("caveat") and len(spot_checks) < 2:
            spot_checks.append(f)
    seen_patterns = {f["flow_pattern"] for f in spot_checks}
    for f in flows:
        if f["flow_pattern"] not in seen_patterns:
            seen_patterns.add(f["flow_pattern"])
            spot_checks.append(f)
    for f in flows:
        if len(spot_checks) >= 6:
            break
        if f not in spot_checks:
            spot_checks.append(f)

    for f in spot_checks:
        print(json.dumps(f, indent=2, ensure_ascii=False))
        print("---")


if __name__ == "__main__":
    main()
