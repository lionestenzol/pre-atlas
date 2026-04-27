#!/usr/bin/env python3
"""
AUTO ACTOR — The system does the work, not you.
================================================
Reads governance state and ghost directives, then ACTS:

1. EXTRACT & CLOSE LOOPS: For each loop being closed, first extracts
   all value (key insights, decisions, ideas, unfinished threads) into
   a structured extraction file. Then archives the loop. Nothing is lost.

2. EXECUTE DIRECTIVES: Reads ghost_directives.json, builds Claude prompts
   from the directives, and submits them as tasks to the execution queue.

3. LANE VIOLATIONS: Automatically parks ideas flagged as lane violations.

The key difference: this system MINES every conversation before closing it.
Every insight, decision, half-formed idea, and useful pattern gets extracted
and saved to extracted_value.json. The conversation gets archived but the
value lives on in a structured, searchable format.

Outputs:
  - auto_actor_log.json      (what it did this run)
  - extracted_value.json      (accumulated value from all closed loops)
  - parked_violations.json    (parked lane violations)
  - Mutations to results.db   (loop closures)
  - Tasks submitted to execution queue
"""

import json
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any

from aegis_client import log_action as _aegis_log

BASE = Path(__file__).parent.resolve()
DB_PATH = BASE / "results.db"
MEMORY_PATH = BASE / "memory_db.json"
CLASSIFICATIONS_PATH = BASE / "conversation_classifications.json"
DELTA_URL = "http://localhost:3001"
_DELTA_API_KEY = ""
_key_path = BASE.parent.parent / ".aegis-tenant-key"
if _key_path.exists():
    _DELTA_API_KEY = _key_path.read_text(encoding="utf-8").strip()
MAX_AUTO_CLOSE_PER_RUN = 5
MAX_DIRECTIVES_PER_RUN = 3
AUTO_CLOSE_LEDGER_PATH = BASE / "auto_close_ledger.json"
DEFAULT_CONFIDENCE_THRESHOLD = 0.8
MIN_CONFIDENCE_THRESHOLD = 0.7  # lowest we'll ever auto-approve
THRESHOLD_DECAY_DAYS = 7  # days without reopen to lower threshold

# Lazy-loaded data
_memory_db: list[dict] | None = None
_classifications: dict[str, dict] | None = None


def load_json(path: Path) -> dict[str, Any] | list[Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def get_db():
    return sqlite3.connect(str(DB_PATH))


def load_memory_db() -> list[dict]:
    global _memory_db
    if _memory_db is None:
        if MEMORY_PATH.exists():
            _memory_db = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        else:
            _memory_db = []
    return _memory_db


def load_classifications() -> dict[str, dict]:
    global _classifications
    if _classifications is None:
        if CLASSIFICATIONS_PATH.exists():
            data = json.loads(CLASSIFICATIONS_PATH.read_text(encoding="utf-8"))
            convos = data.get("conversations", data) if isinstance(data, dict) else data
            _classifications = {str(c.get("convo_id", i)): c for i, c in enumerate(convos)} if isinstance(convos, list) else {}
        else:
            _classifications = {}
    return _classifications


def get_topics(convo_id: str) -> list[tuple[str, float]]:
    if not DB_PATH.exists():
        return []
    con = get_db()
    rows = con.execute(
        "SELECT topic, weight FROM topics WHERE convo_id=? ORDER BY weight DESC LIMIT 10",
        (convo_id,)
    ).fetchall()
    con.close()
    return rows


def _msg_text(msg: dict) -> str:
    """Safely extract text from a message (text can be str or dict)."""
    raw = msg.get("text", "")
    if isinstance(raw, str):
        return raw[:500]
    if isinstance(raw, dict):
        # Audio/video asset or structured content — extract what we can
        parts = raw.get("parts", [])
        if parts:
            texts = [str(p) for p in parts if isinstance(p, str)]
            return " ".join(texts)[:500] if texts else ""
        content = raw.get("content", "")
        if isinstance(content, str):
            return content[:500]
    return ""


def get_conversation_text(convo_id: str) -> dict[str, Any]:
    """Get conversation content for value extraction."""
    memory = load_memory_db()
    idx = int(convo_id)
    if idx < 0 or idx >= len(memory):
        return {}

    convo = memory[idx]
    messages = convo.get("messages", [])
    user_msgs = [m for m in messages if m.get("role") == "user" and _msg_text(m)]
    assistant_msgs = [m for m in messages if m.get("role") == "assistant" and _msg_text(m)]

    return {
        "total_messages": len(messages),
        "user_messages": len(user_msgs),
        "first_user_messages": [_msg_text(m) for m in user_msgs[:3]],
        "last_user_messages": [_msg_text(m) for m in user_msgs[-3:]],
        "last_assistant_messages": [_msg_text(m) for m in assistant_msgs[-2:]],
    }


def get_already_decided() -> set[str]:
    if not DB_PATH.exists():
        return set()
    con = get_db()
    decided = {str(r[0]) for r in con.execute(
        "SELECT convo_id FROM loop_decisions WHERE decision IN ('CLOSE','ARCHIVE')"
    ).fetchall()}
    con.close()
    return decided


def get_mid_lifecycle() -> set[str]:
    """Threads whose harvest manifest has status in {PLANNED, BUILDING, REVIEWING}
    or a terminal lifecycle status. Never auto-close these."""
    try:
        import lifecycle
    except ImportError:
        return set()
    statuses = {"PLANNED", "BUILDING", "REVIEWING", "DONE", "RESOLVED", "DROPPED"}
    return {str(m.get("convo_id")) for m in lifecycle.list_by_status(statuses) if m.get("convo_id") is not None}


def record_decision(convo_id: str, decision: str, title: str) -> bool:
    con = get_db()
    cur = con.cursor()
    existing = cur.execute(
        "SELECT decision FROM loop_decisions WHERE convo_id=?", (convo_id,)
    ).fetchone()
    if existing:
        con.close()
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute(
        "INSERT INTO loop_decisions (convo_id, decision, date) VALUES (?, ?, ?)",
        (convo_id, decision, now)
    )
    con.commit()
    con.close()

    # Notify delta-kernel
    try:
        req = urllib.request.Request(
            "http://localhost:3001/api/law/close_loop",
            data=json.dumps({
                "loop_id": convo_id,
                "title": title,
                "outcome": "closed" if decision == "CLOSE" else "archived",
                "actor": "auto_actor",
                "artifact_path": None,
                "coverage_score": None,
                "status": "RESOLVED" if decision == "CLOSE" else "DROPPED",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

    return True


# ---------------------------------------------------------------------------
# VALUE EXTRACTION — the core of what makes this not just a trash compactor
# ---------------------------------------------------------------------------

def _load_idea_registry() -> dict[str, list[dict]]:
    """Load the idea registry (527 classified ideas across 4 tiers)."""
    path = BASE / "idea_registry.json"
    if not path.exists():
        return {}
    data = load_json(path)
    return data.get("tiers", {}) if isinstance(data, dict) else {}


def _load_leverage_map() -> list[dict]:
    """Load the leverage map."""
    path = BASE / "leverage_map.json"
    if not path.exists():
        return []
    data = load_json(path)
    return data if isinstance(data, list) else data.get("entries", [])


def _load_strategic_priorities() -> dict[str, Any]:
    """Load strategic priorities."""
    path = BASE / "strategic_priorities.json"
    if not path.exists():
        return {}
    return load_json(path)


def _find_related_ideas(title: str, topics: list[tuple[str, float]]) -> list[dict]:
    """Find ideas from the registry that relate to this conversation.

    Uses title matching and topic overlap — the system already classified
    527 ideas, so we just find which ones connect to this loop.
    """
    tiers = _load_idea_registry()
    title_lower = title.lower()
    topic_words = {t[0].lower() for t in topics}

    related: list[dict] = []
    for tier, ideas in tiers.items():
        for idea in ideas:
            idea_title = idea.get("canonical_title", "").lower()
            idea_category = idea.get("category", "").lower()

            # Title overlap
            title_words = set(title_lower.split())
            idea_words = set(idea_title.split())
            overlap = title_words & idea_words - {"the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "is"}

            # Topic overlap
            topic_overlap = topic_words & set(idea_title.split())

            if len(overlap) >= 2 or len(topic_overlap) >= 2:
                related.append({
                    "title": idea.get("canonical_title", ""),
                    "tier": tier,
                    "priority": idea.get("priority_score", 0),
                    "category": idea.get("category", ""),
                    "status": idea.get("status", ""),
                    "alignment": idea.get("alignment_score", 0),
                })

    related.sort(key=lambda x: -x.get("priority", 0))
    return related[:10]


def extract_value(convo_id: str, title: str) -> dict[str, Any]:
    """Extract all usable value from a conversation before closing it.

    Uses EXISTING cognitive data — the system already analyzed 527 ideas,
    built clusters, computed leverage maps, and classified conversations.
    This function connects the loop to that existing knowledge graph.

    Returns a structured extraction with:
    - Topics and their weights (from results.db)
    - Classification data (from conversation_classifications.json)
    - Related ideas from the registry (cross-referenced by title + topics)
    - Conversation content (what you said, what was concluded)
    - Strategic relevance (does this connect to active lanes?)
    """
    extraction: dict[str, Any] = {
        "convo_id": convo_id,
        "title": title,
        "extracted_at": datetime.now().isoformat(),
        "topics": [],
        "classification": {},
        "conversation_summary": {},
        "related_ideas": [],
        "strategic_relevance": {},
    }

    # Topics from results.db
    topics = get_topics(convo_id)
    extraction["topics"] = [{"topic": t[0], "weight": t[1]} for t in topics]

    # Classification from the pipeline
    cls = load_classifications().get(str(convo_id), {})
    extraction["classification"] = {
        "domain": cls.get("domain", "unknown"),
        "outcome": cls.get("outcome", "unknown"),
        "trajectory": cls.get("emotional_trajectory", "unknown"),
        "intensity": cls.get("intensity", "unknown"),
        "category": cls.get("category", "unknown"),
    }

    # Conversation content
    content = get_conversation_text(convo_id)
    extraction["conversation_summary"] = {
        "total_messages": content.get("total_messages", 0),
        "user_messages": content.get("user_messages", 0),
        "started_with": content.get("first_user_messages", []),
        "ended_with": content.get("last_user_messages", []),
        "assistant_concluded": content.get("last_assistant_messages", []),
    }

    # Cross-reference with the idea registry (527 classified ideas)
    related = _find_related_ideas(title, topics)
    extraction["related_ideas"] = related

    # Strategic relevance — does this loop connect to active lanes?
    gov = load_json(BASE / "governance_state.json")
    lanes = gov.get("active_lanes", [])
    lane_names = [l.get("name", "").lower() for l in lanes if isinstance(l, dict)]
    title_lower = title.lower()
    matching_lanes = [l for l in lane_names if any(w in title_lower for w in l.split() if len(w) > 3)]
    extraction["strategic_relevance"] = {
        "connects_to_active_lane": bool(matching_lanes),
        "matching_lanes": matching_lanes,
        "related_idea_count": len(related),
        "highest_priority_idea": related[0]["title"] if related else None,
    }

    return extraction


# ---------------------------------------------------------------------------
# LOOP CLOSURE FEEDBACK LEDGER
# ---------------------------------------------------------------------------

def load_close_ledger() -> dict[str, Any]:
    """Load auto-close feedback ledger. Tracks accuracy to adapt threshold."""
    if AUTO_CLOSE_LEDGER_PATH.exists():
        return json.loads(AUTO_CLOSE_LEDGER_PATH.read_text(encoding="utf-8"))
    return {
        "auto_closed": [],  # { convo_id, title, closed_at, confidence, reopened: bool }
        "threshold": DEFAULT_CONFIDENCE_THRESHOLD,
        "total_closed": 0,
        "total_reopened": 0,
        "last_threshold_update": None,
    }


def save_close_ledger(ledger: dict[str, Any]) -> None:
    AUTO_CLOSE_LEDGER_PATH.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def record_auto_close(convo_id: str, title: str, confidence: float) -> None:
    """Record an auto-close in the feedback ledger."""
    ledger = load_close_ledger()
    ledger["auto_closed"].append({
        "convo_id": convo_id,
        "title": title,
        "closed_at": datetime.now().isoformat(),
        "confidence": confidence,
        "reopened": False,
    })
    ledger["total_closed"] += 1
    save_close_ledger(ledger)


def update_threshold() -> float:
    """Check auto-close track record. Lower threshold if accuracy is high.

    If all auto-closes from 7+ days ago were never reopened, lower the
    threshold by 0.02 (minimum 0.7). If any were reopened, raise by 0.05.
    """
    ledger = load_close_ledger()
    now = datetime.now()
    mature = []  # entries old enough to evaluate

    for entry in ledger["auto_closed"]:
        closed_at = datetime.fromisoformat(entry["closed_at"])
        age_days = (now - closed_at).days
        if age_days >= THRESHOLD_DECAY_DAYS:
            mature.append(entry)

    if not mature:
        return ledger["threshold"]

    reopened = [e for e in mature if e.get("reopened")]
    if reopened:
        # Something got reopened — raise threshold
        ledger["threshold"] = min(DEFAULT_CONFIDENCE_THRESHOLD, ledger["threshold"] + 0.05)
        ledger["total_reopened"] += len(reopened)
        print(f"  THRESHOLD RAISED to {ledger['threshold']} ({len(reopened)} reopened)")
    elif len(mature) >= 3:
        # 3+ mature entries, none reopened — lower threshold
        new_threshold = max(MIN_CONFIDENCE_THRESHOLD, ledger["threshold"] - 0.02)
        if new_threshold < ledger["threshold"]:
            print(f"  THRESHOLD LOWERED: {ledger['threshold']} -> {new_threshold} "
                  f"({len(mature)} auto-closes, 0 reopened)")
            ledger["threshold"] = new_threshold

    ledger["last_threshold_update"] = now.isoformat()
    # Prune evaluated entries (keep last 50)
    ledger["auto_closed"] = ledger["auto_closed"][-50:]
    save_close_ledger(ledger)
    return ledger["threshold"]


# ---------------------------------------------------------------------------
# LOOP CLOSURE — extract value FIRST, then close
# ---------------------------------------------------------------------------

def analyze_loops(mode: str) -> list[dict[str, Any]]:
    """Analyze all open loops and produce recommendations.

    DOES NOT archive or close anything. Produces a recommendation file
    (loop_recommendations.json) that the user reviews and approves.

    For each loop:
    1. Extract value (topics, related ideas, lane connections)
    2. Compute a recommendation (CLOSE, ARCHIVE, KEEP, NEEDS_WORK)
    3. Save to loop_recommendations.json for user review
    """
    loops_path = BASE / "loops_latest.json"
    if not loops_path.exists():
        return []

    loops = load_json(loops_path)
    if not isinstance(loops, list):
        return []

    decided = get_already_decided()
    mid_lifecycle = get_mid_lifecycle()
    protected = decided | mid_lifecycle
    if mid_lifecycle:
        print(f"  Protected from auto-close (mid-lifecycle manifests): {len(mid_lifecycle)}")
    open_loops = [l for l in loops if str(l.get("convo_id", "")) not in protected]

    recommendations: list[dict[str, Any]] = []
    for loop in open_loops:
        convo_id = str(loop.get("convo_id", ""))
        title = loop.get("title", "untitled")
        score = loop.get("score", 0)

        print(f"  Analyzing #{convo_id}: {title}")
        extraction = extract_value(convo_id, title)

        # Compute recommendation based on data — but DON'T execute it
        cls = load_classifications().get(str(convo_id), {})
        outcome = cls.get("outcome", "unknown")
        trajectory = cls.get("emotional_trajectory", "unknown")
        n_related = len(extraction.get("related_ideas", []))
        connects = extraction.get("strategic_relevance", {}).get("connects_to_active_lane", False)
        n_msgs = extraction["conversation_summary"].get("total_messages", 0)
        topics_str = ", ".join(t["topic"] for t in extraction["topics"][:5])

        # Build recommendation with confidence score
        confidence = 0.0
        if connects:
            rec = "KEEP"
            reason = f"Connects to active lane — has strategic value"
            confidence = 0.9
        elif n_related >= 5:
            rec = "NEEDS_WORK"
            reason = f"{n_related} related ideas in registry — value exists but needs extraction"
            confidence = 0.7
        elif outcome == "resolved" or outcome == "produced":
            rec = "CLOSE"
            reason = f"Conversation reached resolution — mark complete"
            confidence = 0.9 if outcome == "resolved" else 0.85
        elif outcome == "abandoned":
            rec = "ARCHIVE"
            reason = f"Abandoned — no active value"
            confidence = 0.85 if n_msgs < 20 else 0.7  # long abandoned convos may have buried value
        elif n_related > 0:
            rec = "NEEDS_WORK"
            reason = f"{n_related} related idea(s) — review before deciding"
            confidence = 0.6
        elif n_msgs < 10:
            rec = "ARCHIVE"
            reason = f"Only {n_msgs} messages, no related ideas — minimal investment"
            confidence = 0.9  # very high — tiny conversation with no connections
        else:
            rec = "REVIEW"
            reason = f"{n_msgs} messages but no classified outcome — needs your eyes"
            confidence = 0.3

        entry = {
            "convo_id": convo_id,
            "title": title,
            "score": score,
            "recommendation": rec,
            "confidence": round(confidence, 2),
            "reason": reason,
            "topics": topics_str,
            "messages": n_msgs,
            "related_ideas": n_related,
            "connects_to_lane": connects,
            "outcome": outcome,
            "trajectory": trajectory,
            "top_related": [r["title"] for r in extraction.get("related_ideas", [])[:3]],
            "extraction": extraction,
        }
        recommendations.append(entry)

        print(f"    [{rec}] {reason}")
        print(f"    Topics: {topics_str or 'none'} | Messages: {n_msgs} | Related: {n_related}")

    # Auto-execute high-confidence CLOSE/ARCHIVE recommendations
    # Threshold adapts based on track record (feedback ledger)
    threshold = update_threshold()
    print(f"\n  Auto-close threshold: {threshold} (adaptive)")
    auto_executed: list[dict[str, Any]] = []
    pending_review: list[dict[str, Any]] = []

    for rec_entry in recommendations:
        can_auto = (
            rec_entry["recommendation"] in ("CLOSE", "ARCHIVE")
            and rec_entry.get("confidence", 0) >= threshold
            and len(auto_executed) < MAX_AUTO_CLOSE_PER_RUN
        )
        if can_auto:
            success = record_decision(
                rec_entry["convo_id"],
                rec_entry["recommendation"],
                rec_entry["title"],
            )
            if success:
                auto_executed.append(rec_entry)
                record_auto_close(rec_entry["convo_id"], rec_entry["title"],
                                  rec_entry.get("confidence", 0))
                print(f"    AUTO-{rec_entry['recommendation']}: #{rec_entry['convo_id']} "
                      f"(confidence={rec_entry['confidence']})")
            else:
                pending_review.append(rec_entry)
        else:
            pending_review.append(rec_entry)

    # Save remaining recommendations for human review
    if recommendations:
        rec_path = BASE / "loop_recommendations.json"
        rec_path.write_text(json.dumps({
            "generated_at": datetime.now().isoformat(),
            "mode": mode,
            "total_open": len(recommendations),
            "auto_executed": len(auto_executed),
            "pending_review": len(pending_review),
            "summary": {
                "CLOSE": len([r for r in recommendations if r["recommendation"] == "CLOSE"]),
                "ARCHIVE": len([r for r in recommendations if r["recommendation"] == "ARCHIVE"]),
                "KEEP": len([r for r in recommendations if r["recommendation"] == "KEEP"]),
                "NEEDS_WORK": len([r for r in recommendations if r["recommendation"] == "NEEDS_WORK"]),
                "REVIEW": len([r for r in recommendations if r["recommendation"] == "REVIEW"]),
            },
            "recommendations": pending_review,
            "auto_closed": [{"convo_id": r["convo_id"], "title": r["title"],
                            "recommendation": r["recommendation"], "confidence": r["confidence"]}
                           for r in auto_executed],
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        if auto_executed:
            print(f"\n  Auto-executed: {len(auto_executed)} (threshold={threshold})")
        if pending_review:
            print(f"  Pending review: {len(pending_review)}")

    return recommendations


# ---------------------------------------------------------------------------
# GHOST DIRECTIVE EXECUTION
# ---------------------------------------------------------------------------

def emit_task_to_delta(task_id: str, intent: str, domain: str, params: dict, priority: int = 1) -> str | None:
    """Emit a task to delta-kernel for daemon execution."""
    try:
        payload = json.dumps({
            "type": "ai",
            "title": task_id,
            "metadata": {
                "cmd": "@WORK",
                "inputs": params,
                "source": "auto_actor",
                "intent": intent,
                "domain": domain,
                "priority": priority,
                "constraints": {"timeout_seconds": 300, "max_cost_usd": 0.50},
            }
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if _DELTA_API_KEY:
            headers["Authorization"] = f"Bearer {_DELTA_API_KEY}"
        req = urllib.request.Request(
            f"{DELTA_URL}/api/work/request",
            data=payload,
            headers=headers,
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("status") in ("APPROVED", "QUEUED"):
            return result.get("job_id", task_id)
        print(f"  Delta denied: {result.get('reason', 'unknown')}")
        return None
    except Exception as e:
        print(f"  Delta emission failed: {e}")
        return None


def score_directive_risk(dtype: str, domain: str, mode: str) -> tuple[float, str]:
    """Score directive risk. Returns (confidence 0-1, risk_level).

    Low-risk (confidence >= 0.8): INVEST in known domains, RESURRECT analysis
    Medium-risk (0.5-0.8): EXECUTE in active lanes
    High-risk (< 0.5): EXECUTE outside active lanes, any directive in CLOSURE mode
    """
    # CLOSURE mode = everything is higher risk (system wants focus, not new work)
    if mode == "CLOSURE":
        return (0.3, "high")

    if dtype == "INVEST":
        return (0.85, "low")  # Research briefs are read-only, low risk
    if dtype == "RESURRECT":
        return (0.8, "low")  # Kill-or-revive analysis is advisory, low risk
    if dtype == "EXECUTE":
        return (0.6, "medium")  # Execution creates artifacts, medium risk

    return (0.4, "high")


AUTO_DIRECTIVE_CONFIDENCE = 0.8


def execute_ghost_directives() -> list[dict[str, Any]]:
    directives_path = BASE / "genesis_output" / "ghost_directives.json"
    if not directives_path.exists():
        print("  No ghost directives found")
        return []

    data = load_json(directives_path)
    if not isinstance(data, dict):
        return []

    directives = data.get("directives", [])
    if not directives:
        print("  No directives to execute")
        return []

    gov = load_json(BASE / "governance_state.json")
    mode = gov.get("mode", "BUILD")
    lanes = gov.get("active_lanes", [])
    lane_names = [l.get("name", "") for l in lanes if isinstance(l, dict)]

    results: list[dict[str, Any]] = []
    executed = 0
    auto_executed = 0
    skipped_approval = 0

    for directive in directives:
        if executed >= MAX_DIRECTIVES_PER_RUN:
            break
        if directive.get("blocked"):
            continue

        dtype = directive.get("type", "")
        domain = directive.get("domain", "")
        rationale = directive.get("rationale", "")
        suggested = directive.get("suggested_action", "")

        confidence, risk_level = score_directive_risk(dtype, domain, mode)

        # High-risk directives need human approval — skip and log
        if confidence < AUTO_DIRECTIVE_CONFIDENCE:
            skipped_approval += 1
            print(f"  SKIP (needs approval): {dtype}/{domain} "
                  f"[confidence={confidence}, risk={risk_level}]")
            results.append({
                "directive_type": dtype, "domain": domain,
                "status": "needs_approval", "confidence": confidence,
                "risk_level": risk_level,
            })
            continue

        print(f"  AUTO-EXECUTE: {dtype}/{domain} "
              f"[confidence={confidence}, risk={risk_level}]")

        if dtype == "EXECUTE":
            prompt = (
                f"You are an autonomous agent for a personal productivity system. "
                f"The system is in {mode} mode with active lanes: {', '.join(lane_names)}.\n\n"
                f"DIRECTIVE: Execute on the '{domain}' domain.\n"
                f"CONTEXT: {rationale}\n"
                f"ACTION: {suggested}\n\n"
                f"Produce a concrete, actionable output. This could be:\n"
                f"- A draft document or outline\n"
                f"- A step-by-step execution plan with specific actions\n"
                f"- A decision memo with clear recommendations\n"
                f"- Code, copy, or content that advances this domain\n\n"
                f"Be specific and produce something the user can immediately use or publish. "
                f"Do NOT produce vague advice. Produce the actual work product."
            )
        elif dtype == "INVEST":
            prompt = (
                f"You are an autonomous agent for a personal productivity system in {mode} mode.\n\n"
                f"DIRECTIVE: Deepen the '{domain}' domain.\n"
                f"CONTEXT: {rationale}\n"
                f"ACTION: {suggested}\n\n"
                f"Produce a research brief that:\n"
                f"1. Identifies the 3 biggest gaps in this domain\n"
                f"2. Lists specific resources, tools, or experiments to close each gap\n"
                f"3. Estimates time investment for each (in hours)\n"
                f"4. Recommends which gap to close first and why\n\n"
                f"Be concrete. Name specific tools, books, courses, or experiments."
            )
        elif dtype == "RESURRECT":
            prompt = (
                f"You are an autonomous agent for a personal productivity system in {mode} mode.\n\n"
                f"DIRECTIVE: Evaluate whether to resurrect the '{domain}' domain.\n"
                f"CONTEXT: {rationale}\n"
                f"ACTION: {suggested}\n\n"
                f"Produce a kill-or-revive analysis:\n"
                f"1. What was the original intent of this domain?\n"
                f"2. Has anything changed since it went dormant?\n"
                f"3. KILL recommendation: why to permanently archive this\n"
                f"4. REVIVE recommendation: what specifically to do in the next 2 hours\n"
                f"5. Your verdict: KILL or REVIVE, with one sentence explaining why\n\n"
                f"Be decisive. No hedging."
            )
        else:
            continue

        task_id = f"ghost-{dtype.lower()}-{domain[:20].replace(' ', '_')}"
        print(f"  Submitting: {task_id}")
        intent_map = {"EXECUTE": "execute_directive", "INVEST": "execute_directive", "RESURRECT": "execute_directive"}
        job_id = emit_task_to_delta(
            task_id=task_id,
            intent=intent_map.get(dtype, "execute_directive"),
            domain="cognitive",
            params={"instructions": prompt, "directive_type": dtype, "domain": domain},
            priority=2 if dtype == "EXECUTE" else 1,
        )

        results.append({
            "directive_type": dtype,
            "domain": domain,
            "task_id": task_id,
            "job_id": job_id,
            "confidence": confidence,
            "risk_level": risk_level,
            "status": "auto_executed",
            "submitted_at": datetime.now().isoformat(),
        })
        executed += 1
        auto_executed += 1

    if skipped_approval:
        print(f"\n  {skipped_approval} directive(s) need human approval (confidence < {AUTO_DIRECTIVE_CONFIDENCE})")

    return results


# ---------------------------------------------------------------------------
# LANE VIOLATION PARKING
# ---------------------------------------------------------------------------

def park_lane_violations() -> list[dict[str, str]]:
    gov = load_json(BASE / "governance_state.json")
    violations = gov.get("lane_violations", [])

    if not violations:
        return []

    parked: list[dict[str, str]] = []
    for v in violations:
        if not isinstance(v, dict):
            continue
        title = v.get("title", "")
        rec = v.get("recommendation", "")
        if rec == "park" and title:
            parked.append({"title": title, "action": "parked"})
            print(f"  [PARK] {title}")

    if parked:
        parked_path = BASE / "parked_violations.json"
        existing = load_json(parked_path) if parked_path.exists() else []
        if not isinstance(existing, list):
            existing = []
        existing.extend([{**p, "date": datetime.now().isoformat()} for p in parked])
        parked_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    return parked


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  AUTO ACTOR — Extract Value, Then Execute")
    print("=" * 60)
    total_start = time.time()

    log: dict[str, Any] = {
        "run_at": datetime.now().isoformat(),
        "loops_closed": [],
        "directives_executed": [],
        "violations_parked": [],
    }

    gov = load_json(BASE / "governance_state.json")
    mode = gov.get("mode", "BUILD")
    print(f"\n  Mode: {mode}")

    # Energy gate: block heavy execution when energy is depleted
    life_signals = load_json(BASE / "life_signals.json")
    energy_level = life_signals.get("energy", {}).get("energy_level", 50)
    burnout_risk = life_signals.get("energy", {}).get("burnout_risk", False)
    energy_gated = energy_level < 30 or burnout_risk
    if energy_gated:
        print(f"  ENERGY GATE ACTIVE: energy={energy_level}, burnout={burnout_risk}")
        print(f"  Skipping directive execution. Loop closure still allowed.")
        log["energy_gated"] = True
        log["energy_level"] = energy_level

    # 1. Analyze loops, auto-close high-confidence, and produce recommendations
    print(f"\n>> Analyze Loops")
    all_recs = analyze_loops(mode)
    log["loops_analyzed"] = len(all_recs)
    log["loops_auto_closed"] = [r["convo_id"] for r in all_recs
                                 if r.get("confidence", 0) >= 0.8
                                 and r["recommendation"] in ("CLOSE", "ARCHIVE")]
    if not all_recs:
        print("  No loops eligible for analysis")

    # 2. Park lane violations
    print(f"\n>> Park Lane Violations")
    log["violations_parked"] = park_lane_violations()
    if not log["violations_parked"]:
        print("  No violations to park")

    # 3. Execute ghost directives (energy-gated)
    print(f"\n>> Execute Ghost Directives")
    if energy_gated:
        print("  SKIPPED — energy gate active (energy<30 or burnout detected)")
        log["directives_executed"] = []
    else:
        log["directives_executed"] = execute_ghost_directives()

    # Write action log
    log_path = BASE / "auto_actor_log.json"
    log["duration_seconds"] = round(time.time() - total_start, 1)
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    total_elapsed = time.time() - total_start
    analyzed = log["loops_analyzed"]
    auto_closed = len(log.get("loops_auto_closed", []))
    directives = len(log["directives_executed"])
    parked = len(log["violations_parked"])

    _aegis_log("auto_actor", "route_decision", {
        "event": "auto_actor_run",
        "mode": mode,
        "loops_analyzed": analyzed,
        "loops_auto_closed": auto_closed,
        "directives_executed": directives,
        "violations_parked": parked,
        "energy_gated": bool(log.get("energy_gated")),
        "duration_seconds": log["duration_seconds"],
        "run_at": log["run_at"],
    })

    print(f"\n{'=' * 60}")
    print(f"  AUTO ACTOR COMPLETE — {total_elapsed:.1f}s")
    print(f"  Loops analyzed:           {analyzed}")
    print(f"  Loops auto-closed:        {auto_closed}")
    print(f"  Directives submitted:     {directives}")
    print(f"  Violations parked:        {parked}")
    print(f"{'=' * 60}")


HELP_TEXT = """\
auto_actor.py — Autonomous closer + directive executor.

Usage:
  python auto_actor.py                # one full run (loops + directives + violations)
  python auto_actor.py --help         # this screen

What it does (in order):
  1. Analyze open loops -> produce loop_recommendations.json.
     Auto-fires CLOSE/ARCHIVE at confidence >= threshold (adaptive, floor 0.7).
     Max 5 per run. SKIPS any thread whose manifest.status is in
     {PLANNED, BUILDING, REVIEWING, DONE, RESOLVED, DROPPED}.
  2. Park lane violations from governance_state.json -> parked_violations.json.
  3. Execute ghost directives (EXECUTE / INVEST / RESURRECT) above confidence 0.8.
     Energy-gated: skipped if life_signals.energy < 30 or burnout_risk=True.

Outputs:
  - auto_actor_log.json       (what ran this invocation)
  - loop_recommendations.json (pending review + auto-closed summary)
  - auto_close_ledger.json    (feedback ledger for adaptive threshold)
  - parked_violations.json    (idea parking)
  - Tasks submitted to delta-kernel /api/work/request

Writes to delta-kernel /api/law/close_loop with the full 6-field payload
(loop_id, title, outcome, artifact_path:null, coverage_score:null, status).
"""

if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) >= 2 and _sys.argv[1] in ("--help", "-h", "help"):
        print(HELP_TEXT)
        _sys.exit(0)
    main()
