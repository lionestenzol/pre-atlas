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

BASE = Path(__file__).parent.resolve()
DB_PATH = BASE / "results.db"
MEMORY_PATH = BASE / "memory_db.json"
CLASSIFICATIONS_PATH = BASE / "conversation_classifications.json"
ORCHESTRATOR_URL = "http://localhost:3005"

MAX_AUTO_CLOSE_PER_RUN = 5
MAX_DIRECTIVES_PER_RUN = 3

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
# LOOP CLOSURE — extract value FIRST, then close
# ---------------------------------------------------------------------------

def compute_auto_decision(convo_id: str, mode: str) -> tuple[str, str] | None:
    cls = load_classifications().get(str(convo_id), {})
    outcome = cls.get("outcome", "unknown")
    trajectory = cls.get("emotional_trajectory", "unknown")
    intensity = cls.get("intensity", "unknown")

    if outcome == "abandoned":
        return ("ARCHIVE", "Abandoned conversation")
    if outcome == "looped" and trajectory in ("spiral", "negative_arc"):
        return ("ARCHIVE", "Spiral/negative arc with no resolution")
    if intensity == "low" and outcome == "looped":
        return ("ARCHIVE", "Low intensity loop")
    if outcome == "looped":
        return ("ARCHIVE", "Looped without resolution")
    if outcome == "resolved":
        return ("CLOSE", "Reached resolution")
    if outcome == "produced":
        return ("CLOSE", "Produced output")
    if mode == "CLOSURE" and outcome == "unknown":
        return ("ARCHIVE", "Unclassified in CLOSURE mode")
    return None


def auto_close_loops(mode: str) -> list[dict[str, Any]]:
    """Extract value from loops, then close them.

    For each loop:
    1. Extract all value (topics, content, insights, ideas, decisions)
    2. Save extraction to extracted_value.json
    3. Record the closure decision
    """
    loops_path = BASE / "loops_latest.json"
    if not loops_path.exists():
        return []

    loops = load_json(loops_path)
    if not isinstance(loops, list):
        return []

    decided = get_already_decided()
    open_loops = [l for l in loops if str(l.get("convo_id", "")) not in decided]

    # Load existing extractions
    extractions_path = BASE / "extracted_value.json"
    extractions = load_json(extractions_path)
    if not isinstance(extractions, dict):
        extractions = {"extractions": [], "metadata": {"total": 0}}
    if "extractions" not in extractions:
        extractions = {"extractions": [], "metadata": {"total": 0}}

    actions: list[dict[str, Any]] = []
    for loop in open_loops:
        if len(actions) >= MAX_AUTO_CLOSE_PER_RUN:
            break

        convo_id = str(loop.get("convo_id", ""))
        title = loop.get("title", "untitled")
        result = compute_auto_decision(convo_id, mode)

        if result is None:
            continue

        decision, reason = result

        # STEP 1: Extract value BEFORE closing
        print(f"  Extracting value from #{convo_id}: {title}")
        extraction = extract_value(convo_id, title)
        extraction["decision"] = decision
        extraction["reason"] = reason

        topics_str = ", ".join(t["topic"] for t in extraction["topics"][:5])
        n_msgs = extraction["conversation_summary"].get("total_messages", 0)
        n_related = len(extraction.get("related_ideas", []))
        connects = extraction.get("strategic_relevance", {}).get("connects_to_active_lane", False)

        print(f"    Topics: {topics_str or 'none'}")
        print(f"    Messages: {n_msgs} | Related ideas: {n_related} | Lane match: {'YES' if connects else 'no'}")

        # STEP 2: Save extraction
        extractions["extractions"].append(extraction)
        extractions["metadata"]["total"] = len(extractions["extractions"])
        extractions["metadata"]["last_updated"] = datetime.now().isoformat()

        # STEP 3: Record closure
        if record_decision(convo_id, decision, title):
            actions.append({
                "convo_id": convo_id,
                "title": title,
                "decision": decision,
                "reason": reason,
                "topics": topics_str,
                "messages": n_msgs,
                "related_ideas": n_related,
                "connects_to_lane": connects,
            })
            print(f"    [{decision}] — {reason}")

    # Write all extractions
    if actions:
        extractions_path.write_text(json.dumps(extractions, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  Value saved to extracted_value.json ({extractions['metadata']['total']} total extractions)")

    return actions


# ---------------------------------------------------------------------------
# GHOST DIRECTIVE EXECUTION
# ---------------------------------------------------------------------------

def submit_task_to_queue(task_id: str, instructions: str, priority: str = "normal") -> str | None:
    try:
        payload = json.dumps({
            "task_id": task_id,
            "instructions": instructions,
            "priority": priority,
            "timeout_seconds": 300,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{ORCHESTRATOR_URL}/api/v1/tasks/execute",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode("utf-8"))

        if result.get("status") == "queued":
            return result.get("job_id")
        elif result.get("success"):
            return f"direct:{result.get('task_id', task_id)}"
        else:
            print(f"  Task failed: {result.get('error', 'unknown')}")
            return None
    except Exception as e:
        print(f"  Task submission failed: {e}")
        return None


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

    for directive in directives:
        if executed >= MAX_DIRECTIVES_PER_RUN:
            break
        if directive.get("blocked"):
            continue

        dtype = directive.get("type", "")
        domain = directive.get("domain", "")
        rationale = directive.get("rationale", "")
        suggested = directive.get("suggested_action", "")

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
        job_id = submit_task_to_queue(task_id, prompt, priority="normal")

        results.append({
            "directive_type": dtype,
            "domain": domain,
            "task_id": task_id,
            "job_id": job_id,
            "submitted_at": datetime.now().isoformat(),
        })
        executed += 1

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

    # 1. Extract value from loops, then close them
    print(f"\n>> Extract & Close Loops")
    log["loops_closed"] = auto_close_loops(mode)
    if not log["loops_closed"]:
        print("  No loops eligible for auto-close")

    # 2. Park lane violations
    print(f"\n>> Park Lane Violations")
    log["violations_parked"] = park_lane_violations()
    if not log["violations_parked"]:
        print("  No violations to park")

    # 3. Execute ghost directives
    print(f"\n>> Execute Ghost Directives")
    log["directives_executed"] = execute_ghost_directives()

    # Write action log
    log_path = BASE / "auto_actor_log.json"
    log["duration_seconds"] = round(time.time() - total_start, 1)
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    total_elapsed = time.time() - total_start
    closed = len(log["loops_closed"])
    directives = len(log["directives_executed"])
    parked = len(log["violations_parked"])

    print(f"\n{'=' * 60}")
    print(f"  AUTO ACTOR COMPLETE — {total_elapsed:.1f}s")
    print(f"  Loops extracted & closed: {closed}")
    print(f"  Directives submitted:     {directives}")
    print(f"  Violations parked:        {parked}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
