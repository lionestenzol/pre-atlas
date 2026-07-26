"""Classification: messy input -> one type, one domain, entities, confidence.

Default path is a weighted keyword scorer over the closed enum sets. It is
deterministic, needs no API, and is tuned against the spec's example drops.
If the Anthropic backend is enabled it is tried first and the heuristic is the
fallback. Results are cached by input_hash.
"""

from __future__ import annotations

import re
import time

from . import llm
from .hashing import ClassificationCache
from .schema import TYPES, DOMAINS

# ---- Domain signals (substring, weight). Order independent; scored. -------

_DOMAIN_SIGNALS: dict[str, list[tuple[str, float]]] = {
    "file_ops": [
        ("drive", 3), ("folder", 3), ("files", 3), ("file ", 2), ("metadata", 3),
        ("duplicate", 3), ("directory", 2), ("inventory", 2), ("cleanup", 2),
        ("index", 1), (".py", 2), ("code folder", 3), ("dump", 2),
    ],
    "build_product": [
        ("droplist", 4), ("atlas", 4), ("mini ship", 3), ("mini-ship", 3),
        ("packet", 2), ("claude code", 3), ("claude_code", 3), ("langgraph", 3),
        ("feature", 2), ("bug", 3), ("architecture", 3), ("spec", 2),
        ("refactor", 2), ("endpoint", 2), ("cli", 2), ("dispatcher", 2),
        ("schema", 2), ("vector", 2), ("dag", 2), ("rag", 2), ("app", 1),
        ("classifier", 2), ("crashes", 2), ("crash", 2),
    ],
    "animal_property": [
        ("rabbit", 4), ("goat", 4), ("chicken", 4), ("bsfl", 4), ("hutch", 3),
        ("watermelon", 3), ("vine", 2), ("bedding", 3), ("garden", 3),
        ("field", 2), ("breeding", 3), ("feeding", 2), ("fed the", 3),
        ("limping", 3), ("animal", 2), ("water", 1), ("bins", 2), ("shade", 1),
    ],
    "money_admin": [
        ("bill", 3), ("insurance", 4), ("receipt", 4), ("invoice", 3),
        ("appointment", 3), ("deadline", 3), ("payment", 3), ("renewal", 3),
        ("taxes", 3), ("tax", 2), ("vet", 2), ("$", 3), ("due", 2),
        ("electric bill", 4), ("feed store", 2),
    ],
    "daily_command": [
        ("morning brief", 5), ("morning", 3), ("daily brief", 5), ("brief", 2),
        ("triage", 3), ("my plate", 3), ("today", 1), ("what's on", 2),
    ],
    "people_admin": [
        ("helper", 3), ("contact", 2), ("call ", 1), ("message", 2),
        ("text ", 1), ("email ", 1), ("person", 2),
    ],
    "food_health": [
        ("meal", 3), ("diet", 3), ("recipe", 3), ("workout", 3), ("calorie", 3),
        ("groceries", 2), ("sleep", 2),
    ],
}

# ---- Type signals ---------------------------------------------------------

_TYPE_SIGNALS: dict[str, list[tuple[str, float]]] = {
    "problem": [
        ("burned", 3), ("broke", 2), ("broken", 3), ("crash", 3), ("crashes", 3),
        ("fail", 3), ("error", 3), ("bug", 3), ("issue", 2), ("wrong", 2),
        ("too much", 3), ("higher than usual", 3), ("won't", 2), ("doesn't", 2),
        ("stuck", 2), ("empty", 1),
    ],
    "warning": [
        ("warning", 3), ("urgent", 4), ("danger", 4), ("emergency", 4),
        ("sick", 3), ("dying", 4), ("limping", 4), ("abnormal", 3), ("bleeding", 4),
    ],
    "decision": [
        ("should be treated", 5), ("should be", 3), ("not a ", 3), ("is not", 3),
        ("decided", 4), ("decision", 4), ("treat as", 4), ("treated as", 4),
        ("use plain", 2), ("defer", 2), ("go with", 2), ("instead of", 1),
    ],
    "follow_up": [
        ("follow up", 4), ("follow-up", 4), ("waiting on", 4), ("still waiting", 4),
        ("check back", 3), ("remind", 3), ("get back to", 2),
    ],
    "idea": [
        ("what if", 4), ("could ", 2), ("maybe we", 2), ("idea", 3),
        ("imagine", 2), ("concept", 2), ("might be cool", 2),
    ],
    "reference": [
        ("note:", 4), ("fyi", 3), ("for reference", 4), ("reference", 2),
        ("keep in mind", 2), ("just noting", 2),
    ],
    "log": [
        ("again", 2), ("growing", 2), ("noticed", 2), ("observed", 3),
        ("fed ", 2), ("topped off", 3), ("all normal", 4), ("watered", 2),
        ("today i", 1), ("looked", 1),
    ],
    "project": [
        ("project", 2), ("build out", 3), ("whole system", 2), ("end to end", 2),
    ],
    "asset": [
        ("here's a", 2), ("attached", 3), ("screenshot", 3), ("photo", 2),
        ("link", 1), ("got the", 2), ("notice", 2), ("document", 2),
    ],
    "task": [
        ("need to", 3), ("add a", 3), ("create", 2), ("make ", 2), ("fix ", 3),
        ("clean up", 3), ("move ", 2), ("schedule", 2), ("call the", 2),
        ("set up", 2), ("build a", 2), ("write", 2),
    ],
}

# crude entity extraction: capitalized words, known nouns, dollar amounts, dates
_PROPER = re.compile(r"\b([A-Z][a-zA-Z0-9]+)\b")
_MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?")
_KNOWN_ENTITIES = [
    "DropList", "Atlas", "Mini Ship", "Spark", "Claude Code", "BSFL",
    "Drive", "LangGraph", "USDA", "CLAUDE.md", "Strudel",
]
_STOP_PROPER = {"The", "A", "I", "It", "This", "That", "We", "My", "One",
                "They", "He", "She", "You", "Their", "There", "Then", "But",
                "And", "So", "If", "When", "What", "Got", "Need", "Add", "Use"}


def _score(text: str, signals: dict[str, list[tuple[str, float]]]) -> dict[str, float]:
    low = text.lower()
    scores = {k: 0.0 for k in signals}
    for label, kws in signals.items():
        for kw, w in kws:
            if kw in low:
                scores[label] += w
    return scores


def _extract_entities(text: str) -> list[str]:
    ents: list[str] = []
    for e in _KNOWN_ENTITIES:
        if e.lower() in text.lower() and e not in ents:
            ents.append(e)
    for m in _MONEY.findall(text):
        ents.append(m.strip())
    for m in _PROPER.findall(text):
        if m not in _STOP_PROPER and len(m) > 2 and m not in ents:
            if not any(m.lower() in e.lower() for e in ents):
                ents.append(m)
    return ents[:8]


def _confidence(scores: dict[str, float], winner: str) -> float:
    total = sum(scores.values())
    if total <= 0:
        return 0.35  # nothing matched -> low confidence, likely general
    top = scores[winner]
    ordered = sorted(scores.values(), reverse=True)
    second = ordered[1] if len(ordered) > 1 else 0.0
    margin = (top - second) / top if top else 0.0
    base = top / (total + 1e-9)
    return round(min(0.99, 0.45 + 0.4 * base + 0.15 * margin), 2)


def heuristic_classify(normalized: str) -> dict:
    dom_scores = _score(normalized, _DOMAIN_SIGNALS)
    typ_scores = _score(normalized, _TYPE_SIGNALS)

    domain = max(dom_scores, key=dom_scores.get) if any(dom_scores.values()) else "general"
    dtype = max(typ_scores, key=typ_scores.get) if any(typ_scores.values()) else "task"

    dom_conf = _confidence(dom_scores, domain)
    typ_conf = _confidence(typ_scores, dtype)

    return {
        "type": dtype if dtype in TYPES else "task",
        "domain": domain if domain in DOMAINS else "general",
        "entities": _extract_entities(normalized),
        "confidence": round((dom_conf + typ_conf) / 2, 2),
    }


_LLM_SYSTEM = (
    "You are a strict classifier. Classify the drop into exactly one type and "
    "one domain from the allowed enums. Respond with ONLY a JSON object, no prose.\n"
    f"types: {sorted(TYPES)}\ndomains: {sorted(DOMAINS)}"
)


def classify(normalized: str, input_hash: str, cache: ClassificationCache) -> dict:
    """Return {type, domain, entities, confidence}. Cached by input_hash."""
    cached = cache.get(input_hash)
    if cached and cached.get("type"):
        llm.log_call("classification", "cache", input_hash, normalized, "CACHE HIT", 0, "success")
        return cached

    if llm.anthropic_available():
        user = f'Drop: """{normalized}"""\nReturn JSON: {{"type":"","domain":"","entities":[],"confidence":0.0}}'
        data = llm.call_json("classification", _LLM_SYSTEM, user, input_hash)
        if data and data.get("type") in TYPES and data.get("domain") in DOMAINS:
            result = {
                "type": data["type"],
                "domain": data["domain"],
                "entities": data.get("entities", []) or _extract_entities(normalized),
                "confidence": float(data.get("confidence", 0.8)),
            }
            cache.put(input_hash, result)
            return result

    t0 = time.time()
    result = heuristic_classify(normalized)
    llm.log_call(
        "classification", "heuristic-v1", input_hash, normalized,
        str(result), int((time.time() - t0) * 1000), "success",
    )
    cache.put(input_hash, result)
    return result
