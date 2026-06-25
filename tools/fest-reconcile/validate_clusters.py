"""
Phase 2 · Sequence 03 · validate_clusters

Reads clusters_v1.json + chatgpt_temporal.json + cc_temporal.json.
For each cluster computes:
  - coverage: portfolio items it hits (from v0 already)
  - distinctness: pairwise term-overlap matrix vs all other clusters
  - substring_warning: seed terms shorter than 5 chars that may match
    inside unrelated tokens (FP risk)
  - false_positive_samples: 5 raw match texts per channel for HOTL eyeball

Output: festival_out/clusters_final.json

HOTL principle: emit counts + samples. No auto-classification, no
auto-judgement. Bruke decides which clusters survive, which terms
get pruned, which seeds need tightening.
"""

import json
import random
import sys
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from _match import has_seed_match, _compile_seed  # word-boundary matcher

OUT_DIR = ROOT / "festival_out"
V2 = "--v2" in sys.argv
CLUSTERS_V1 = OUT_DIR / ("clusters_v1_v2.json" if V2 else "clusters_v1.json")
CHATGPT = OUT_DIR / "chatgpt_temporal.json"
CC = OUT_DIR / "cc_temporal.json"
OUT = OUT_DIR / ("clusters_final_v2.json" if V2 else "clusters_final.json")

SAMPLE_COUNT = 5
RANDOM_SEED = 42
SHORT_SEED_THRESHOLD = 5  # seeds < this length get substring-warning check


def compute_pairwise_overlap(clusters):
    """For each cluster, list other clusters and the discovered_terms in common."""
    by_name = {c["name"]: set(t["term"] for t in c["discovered_terms"]) for c in clusters}
    out = {}
    for c in clusters:
        my_terms = by_name[c["name"]]
        overlaps = {}
        for other_name, other_terms in by_name.items():
            if other_name == c["name"]:
                continue
            shared = sorted(my_terms & other_terms)
            overlaps[other_name] = {
                "shared_count": len(shared),
                "shared_terms": shared,
            }
        out[c["name"]] = overlaps
    return out


def substring_warning(cluster, chatgpt_items, cc_items):
    """For each seed shorter than threshold, scan the FULL chatgpt corpus
    (no 2000-item cap) for cases where the seed appears inside a longer
    alphanumeric/underscore token. With word-boundary matching now in effect
    these are warnings only — the match itself won't fire — but they surface
    seeds that v1 would have over-matched, useful for HOTL eyeball.
    """
    warnings = []
    for seed in cluster["seed_terms"]:
        if len(seed) >= SHORT_SEED_THRESHOLD:
            continue
        seed_lc = seed.lower()
        examples = []
        for it in chatgpt_items:  # full corpus, no [:2000] cap
            title = (it.get("title") or "").lower()
            if seed_lc in title:
                idx = title.find(seed_lc)
                left_ok = (idx == 0) or not title[idx - 1].isalnum()
                right_idx = idx + len(seed_lc)
                right_ok = (right_idx >= len(title)) or not title[right_idx].isalnum()
                if not (left_ok and right_ok):
                    examples.append({
                        "channel": "chatgpt",
                        "convo_id": it.get("convo_id"),
                        "title": it.get("title"),
                    })
                    if len(examples) >= 3:
                        break
        if examples:
            warnings.append({
                "seed_term": seed,
                "length": len(seed),
                "fp_examples_in_other_tokens": examples,
                "note": "v1-substring-rule FP detector. v2 uses word-boundary so these examples no longer match in production.",
            })
    return warnings


def sample_match_texts(cluster, chatgpt_items, cc_items, rng):
    seeds_lc = [s.lower() for s in cluster["seed_terms"]]
    compiled = [(s, _compile_seed(s)) for s in seeds_lc]
    cg_matches = []
    cc_matches = []
    for it in chatgpt_items:
        title = (it.get("title") or "")
        tl = title.lower()
        ms = [s for s, rx in compiled if rx.search(tl)]
        if ms:
            cg_matches.append({
                "convo_id": it.get("convo_id"),
                "first_date": it.get("first_date"),
                "title": title,
                "matched_seeds": ms,
            })
    for it in cc_items:
        msg = (it.get("first_user_msg") or "")
        ml = msg.lower()
        ms = [s for s, rx in compiled if rx.search(ml)]
        if ms:
            cc_matches.append({
                "session_id": it.get("session_id"),
                "first_ts": it.get("first_ts"),
                "first_user_msg": msg[:300],
                "matched_seeds": ms,
            })
    cg_sample = rng.sample(cg_matches, min(SAMPLE_COUNT, len(cg_matches)))
    cc_sample = rng.sample(cc_matches, min(SAMPLE_COUNT, len(cc_matches)))
    return cg_sample, cc_sample


def main():
    v1 = json.loads(CLUSTERS_V1.read_text(encoding="utf-8"))
    chatgpt = json.loads(CHATGPT.read_text(encoding="utf-8"))["items"]
    cc = json.loads(CC.read_text(encoding="utf-8"))["items"]

    overlap_matrix = compute_pairwise_overlap(v1["clusters"])

    rng = random.Random(RANDOM_SEED)
    enriched = []
    for c in v1["clusters"]:
        warnings = substring_warning(c, chatgpt, cc)
        cg_sample, cc_sample = sample_match_texts(c, chatgpt, cc, rng)
        enriched.append({
            **c,
            "validation": {
                "coverage": {
                    "portfolio_hit_count": c["portfolio_hit_count"],
                    "chatgpt_match_count": c["chatgpt_match_count"],
                    "cc_match_count": c["cc_match_count"],
                },
                "distinctness": overlap_matrix[c["name"]],
                "substring_warnings": warnings,
                "false_positive_samples": {
                    "method": (
                        f"random.sample with seed={RANDOM_SEED} from "
                        "matching texts. HOTL eyeballs to confirm or "
                        "reject cluster membership."
                    ),
                    "chatgpt_samples": cg_sample,
                    "cc_samples": cc_sample,
                },
            },
        })

    out = {
        "phase": "002_KEYWORD_CLUSTERS",
        "sequence": "03_validate_clusters",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "method": (
            "Compute portfolio + corpus coverage, pairwise term-overlap "
            "matrix across all clusters, and a deterministic 5-sample "
            "per channel of match texts. Short-seed substring warnings "
            "flag seeds <5 chars that appeared inside unrelated tokens. "
            "All numbers + samples emitted; no auto-classification."
        ),
        "sample_count_per_channel": SAMPLE_COUNT,
        "random_seed": RANDOM_SEED,
        "short_seed_threshold": SHORT_SEED_THRESHOLD,
        "clusters": enriched,
    }

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"WROTE {OUT}")
    print()
    print("Coverage + distinctness summary:")
    for c in enriched:
        v = c["validation"]
        d = v["distinctness"]
        max_overlap = max((d[k]["shared_count"] for k in d), default=0)
        max_pair = max(d.items(), key=lambda kv: kv[1]["shared_count"], default=(None, {"shared_count": 0}))
        cov = v["coverage"]
        warns = len(v["substring_warnings"])
        print(
            f"  {c['name']:24s} "
            f"portfolio={cov['portfolio_hit_count']:3d}  "
            f"cg={cov['chatgpt_match_count']:5d}  "
            f"cc={cov['cc_match_count']:4d}  "
            f"max_overlap={max_overlap:2d} (with {max_pair[0]})  "
            f"warnings={warns}"
        )


if __name__ == "__main__":
    main()
