"""
Phase 2 · Sequence 02 · expand_clusters_from_corpus

Reads clusters_v0.json + chatgpt_temporal.json + cc_temporal.json.
For each cluster: scan ChatGPT titles + CC first_user_msgs for matches on
any seed term. From the matching texts, tokenize and rank co-occurring
terms by frequency (per channel). Emit discovered_terms with provenance.

Output: festival_out/clusters_v1.json

Method:
- Substring match (case-insensitive) of any seed term against each text
- Tokenize matching text on non-word boundaries, lowercase
- Drop stopwords + the cluster's own seed terms + short tokens + pure digits
- Top 30 co-occurring tokens per channel per cluster
- Cap sample IDs at 5 per discovered term per channel (compact provenance)

HOTL: counts + samples emitted, no auto-promotion of discovered terms
into the cluster (Seq 03 validates).
"""

import json
import re
import sys
import datetime as dt
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from _match import has_seed_match  # word-boundary substring matcher

OUT_DIR = ROOT / "festival_out"
V2 = "--v2" in sys.argv
CLUSTERS_V0 = OUT_DIR / ("clusters_v0_v2.json" if V2 else "clusters_v0.json")
CHATGPT = OUT_DIR / "chatgpt_temporal.json"
CC = OUT_DIR / "cc_temporal.json"
OUT = OUT_DIR / ("clusters_v1_v2.json" if V2 else "clusters_v1.json")

STOPWORDS = {
    # english core
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "had",
    "are", "was", "were", "but", "not", "you", "your", "yours", "what", "which",
    "who", "whom", "why", "how", "when", "where", "all", "any", "some", "one",
    "two", "three", "few", "more", "most", "other", "into", "out", "over",
    "under", "again", "off", "down", "up", "now", "then", "than", "too",
    "very", "can", "will", "just", "should", "would", "could", "may", "might",
    "must", "shall", "did", "does", "doing", "done", "been", "being", "they",
    "them", "their", "theirs", "she", "her", "hers", "him", "his", "its",
    "we", "us", "our", "ours", "me", "my", "mine", "i", "a", "an", "is",
    "in", "on", "of", "to", "at", "by", "as", "if", "or", "be", "do", "it",
    "so", "no", "yes", "ok", "let", "get", "got", "make", "made", "want",
    "need", "want", "going", "go", "goes", "went", "set", "use", "used",
    "using", "uses", "way", "see", "look", "looking", "show", "tell", "told",
    "give", "given", "take", "took", "find", "found", "ask", "asked", "asking",
    "thing", "things", "stuff", "much", "many", "back", "still", "even",
    "also", "like", "like", "really", "actually", "basically",
    # tooling chatter
    "claude", "code", "claude-code", "cc", "session", "sessions", "chat",
    "convo", "thread", "user", "assistant", "agent", "tool", "tools",
    "function", "method", "class", "file", "files", "line", "lines",
    "path", "paths", "dir", "directory", "folder", "project", "repo",
    "repository", "branch", "commit", "commits", "pr", "git", "github",
    "main", "master", "src", "test", "tests", "node", "npm", "py", "ts",
    "js", "tsx", "jsx", "json", "html", "css", "md", "txt",
    "build", "run", "running", "ran", "start", "started", "stop", "stopped",
    "fix", "fixed", "fixing", "fixes", "bug", "bugs", "error", "errors",
    "issue", "issues", "problem", "problems", "feature", "features",
    "work", "working", "worked", "works", "task", "tasks", "step", "steps",
    "next", "first", "last", "new", "old", "good", "bad", "right", "wrong",
    "well", "best", "better", "small", "big", "large", "long", "short",
    "quick", "slow", "fast", "current", "current", "ready", "done",
    # filler
    "wanna", "gonna", "kinda", "sorta", "yeah", "nah", "huh", "lol", "rn",
    "tho", "tbh", "imo", "fyi", "etc", "vs", "via", "per",
    # punctuation-ish leftovers
    "s", "t", "d", "ll", "ve", "re", "m",
    # mode names (already in atlas_core seeds, but we filter for everyone)
    "recover", "closure", "maintenance", "compound", "scale",
    # path / fs noise from CC first_user_msgs that embed file paths
    "bruke", "users", "pre", "worktree", "worktrees", "appdata", "roaming",
    "windows", "win32", "powershell", "ps1", "bash", "sh", "exe",
    # weapon/mission scaffold template tokens (boilerplate, not topic)
    "mission", "scope", "target", "single", "expansion",
    "automated", "scheduled", "scheduled-task", "scheduled-tasks",
    "phase", "phases", "sequence", "sequences", "context",
    # generic process language (high-frequency, low-signal)
    "read", "name", "names", "explore", "understand",
    "deep", "called",
    "pass", "only",
    "existing", "thinking", "already",
    # already-cluster-named (in productivity_skills seeds, but appear cross-cluster)
    "weapon",
}

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")
TOP_N = 30
MAX_SAMPLES = 5


def tokenize(text):
    if not text:
        return []
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


# has_seed_match imported from _match (word-boundary regex). Local substring
# version removed; this fixes the v1 bug where seed 'stem' matched inside
# 'system' / 'ecosystem'.


def expand_one(cluster, chatgpt_items, cc_items):
    seeds_lc = [s.lower() for s in cluster["seed_terms"]]
    seed_token_set = set()
    for s in seeds_lc:
        seed_token_set.update(tokenize(s))

    chatgpt_match_ids = []
    chatgpt_token_counts = Counter()
    chatgpt_token_samples = defaultdict(list)

    for it in chatgpt_items:
        title = it.get("title", "") or ""
        if has_seed_match(title, seeds_lc):
            cid = it.get("convo_id")
            chatgpt_match_ids.append(cid)
            for tok in tokenize(title):
                if tok in STOPWORDS or tok in seed_token_set:
                    continue
                chatgpt_token_counts[tok] += 1
                if len(chatgpt_token_samples[tok]) < MAX_SAMPLES:
                    chatgpt_token_samples[tok].append(cid)

    cc_match_ids = []
    cc_token_counts = Counter()
    cc_token_samples = defaultdict(list)

    for it in cc_items:
        msg = it.get("first_user_msg", "") or ""
        if has_seed_match(msg, seeds_lc):
            sid = it.get("session_id")
            cc_match_ids.append(sid)
            for tok in tokenize(msg):
                if tok in STOPWORDS or tok in seed_token_set:
                    continue
                cc_token_counts[tok] += 1
                if len(cc_token_samples[tok]) < MAX_SAMPLES:
                    cc_token_samples[tok].append(sid)

    chatgpt_top = chatgpt_token_counts.most_common(TOP_N)
    cc_top = cc_token_counts.most_common(TOP_N)

    union_tokens = set(t for t, _ in chatgpt_top) | set(t for t, _ in cc_top)
    discovered = []
    for tok in union_tokens:
        discovered.append({
            "term": tok,
            "chatgpt_count": chatgpt_token_counts.get(tok, 0),
            "cc_count": cc_token_counts.get(tok, 0),
            "chatgpt_samples": chatgpt_token_samples.get(tok, []),
            "cc_samples": cc_token_samples.get(tok, []),
        })
    discovered.sort(
        key=lambda d: (d["chatgpt_count"] + d["cc_count"], d["chatgpt_count"]),
        reverse=True,
    )
    discovered = discovered[:TOP_N]

    return {
        **cluster,
        "chatgpt_match_count": len(chatgpt_match_ids),
        "cc_match_count": len(cc_match_ids),
        "chatgpt_sample_ids": chatgpt_match_ids[:10],
        "cc_sample_ids": cc_match_ids[:10],
        "discovered_terms": discovered,
    }


def main():
    v0 = json.loads(CLUSTERS_V0.read_text(encoding="utf-8"))
    chatgpt = json.loads(CHATGPT.read_text(encoding="utf-8"))
    cc = json.loads(CC.read_text(encoding="utf-8"))

    enriched = [expand_one(c, chatgpt["items"], cc["items"]) for c in v0["clusters"]]

    out = {
        "phase": "002_KEYWORD_CLUSTERS",
        "sequence": "02_expand_clusters_from_corpus",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "method": (
            "Substring-match each cluster's seed terms against chatgpt "
            "titles + cc first_user_msgs. From matching texts, tokenize "
            "and rank co-occurring terms after stopword + seed-token "
            "filtering. Top 30 per cluster (union of channel tops), "
            "5 sample IDs per term per channel."
        ),
        "stopword_count": len(STOPWORDS),
        "top_n": TOP_N,
        "max_samples_per_term": MAX_SAMPLES,
        "clusters": enriched,
    }

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"WROTE {OUT}")
    for c in enriched:
        cg = c["chatgpt_match_count"]
        cc_ = c["cc_match_count"]
        d = len(c["discovered_terms"])
        print(f"  {c['name']:24s} chatgpt_match={cg:5d}  cc_match={cc_:4d}  discovered={d}")


if __name__ == "__main__":
    main()
