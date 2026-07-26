#!/usr/bin/env python3
"""Atlas profile fan-out — headless setup for the whole behavioral system.

Reads a single behavioral profile (routines + A/B/C day types + focus areas +
mission) and pushes it to the one hub every surface reads from: the delta-kernel
cycleboard state at PUT /api/cycleboard. Because the inPACT app, the inPACT CLI,
cortex's morning/midday/evening cadence, and the delta-kernel CLIs (atlas.ts,
atlas-ai.ts) all read that same blob, one apply propagates everywhere.

No browser, no wizard, no pip installs (stdlib only). Idempotent and re-runnable.

Usage:
    python setup/apply.py                         # apply the active profile
    python setup/apply.py --dry-run               # print the resulting blob, do not write
    python setup/apply.py --profile PATH          # use a different profile file
    python setup/apply.py --reset                 # BLANK CANVAS: wipe runtime data too
    python setup/apply.py --api http://127.0.0.1:3001

Exit codes: 0 ok, 1 validation error, 2 network/hub error.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_PROFILE = HERE / "atlas_profile.json"
DEFAULT_API = "http://127.0.0.1:3001"
TIMEOUT_S = 10

# Cycleboard state keys that hold accumulated runtime data we must NOT clobber on
# a normal apply (only --reset wipes them). Everything else is template-controlled.
RUNTIME_KEYS = (
    "DayPlans", "Journal", "History", "MomentumWins", "Reflections",
    "WeeklyPlan", "EightSteps", "Today", "_OrchestratorMeta",
)


# --------------------------------------------------------------------------- IO

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_profile(path: Path) -> dict[str, Any]:
    """Load + strip underscore-prefixed comment keys."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


# -------------------------------------------------------------------- validate

def validate_profile(profile: dict[str, Any]) -> list[str]:
    """Fail-loud structural validation. Returns a list of human-readable errors."""
    errors: list[str] = []

    identity = profile.get("identity")
    if not isinstance(identity, dict):
        errors.append("identity: missing or not an object")
    else:
        for key in ("mission", "motto"):
            if not isinstance(identity.get(key), str):
                errors.append(f"identity.{key}: must be a string (may be empty)")

    routines = profile.get("routines")
    if not isinstance(routines, dict):
        errors.append("routines: missing or not an object")
    else:
        for name, steps in routines.items():
            if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
                errors.append(f"routines.{name}: must be a list of strings")

    day_types = profile.get("day_types")
    if not isinstance(day_types, dict) or not day_types:
        errors.append("day_types: missing or empty (need at least one, e.g. 'A')")
    else:
        routine_names = set(routines) if isinstance(routines, dict) else set()
        for letter, dt in day_types.items():
            if not isinstance(dt, dict):
                errors.append(f"day_types.{letter}: not an object")
                continue
            if not isinstance(dt.get("name"), str) or not dt["name"]:
                errors.append(f"day_types.{letter}.name: required non-empty string")
            for rn in dt.get("routines", []):
                if rn not in routine_names:
                    errors.append(
                        f"day_types.{letter}.routines: '{rn}' is not defined in routines"
                    )
            for i, b in enumerate(dt.get("time_blocks", [])):
                if not isinstance(b, dict) or "time" not in b or "title" not in b:
                    errors.append(f"day_types.{letter}.time_blocks[{i}]: need 'time' and 'title'")

    settings = profile.get("settings") or {}
    default_dt = settings.get("default_day_type")
    if default_dt and isinstance(day_types, dict) and default_dt not in day_types:
        errors.append(f"settings.default_day_type: '{default_dt}' is not a defined day_type")

    return errors


# ----------------------------------------------------------------- build state

def build_state_fields(profile: dict[str, Any]) -> dict[str, Any]:
    """Map the clean snake_case profile to the camelCase keys the app expects."""
    identity = profile.get("identity", {})
    settings = profile.get("settings", {})

    focus_area = [
        {
            "id": f"fa{i + 1}",
            "name": fa["name"],
            "definition": fa.get("definition", ""),
            "color": fa.get("color", "#3B82F6"),
            "tasks": [],
        }
        for i, fa in enumerate(profile.get("focus_areas", []))
    ]

    day_type_templates = {
        letter: {
            "name": dt.get("name", letter),
            "description": dt.get("description", ""),
            "timeBlocks": [
                {"time": b["time"], "title": b["title"], "duration": b.get("duration", 0)}
                for b in dt.get("time_blocks", [])
            ],
            "routines": list(dt.get("routines", [])),
            "goals": {
                "baseline": (dt.get("goals") or {}).get("baseline", ""),
                "stretch": (dt.get("goals") or {}).get("stretch", ""),
            },
        }
        for letter, dt in profile.get("day_types", {}).items()
    }

    az_task = [
        {
            "id": f"seed-{t['letter'].lower()}",
            "letter": t["letter"],
            "task": t["task"],
            "status": t.get("status", "Not Started"),
            "notes": t.get("notes", ""),
            "createdAt": _now(),
        }
        for t in profile.get("az_tasks", [])
    ]

    return {
        "Routine": dict(profile.get("routines", {})),
        "DayTypeTemplates": day_type_templates,
        "FocusArea": focus_area,
        "AZTask": az_task,
        "Contingencies": profile.get("contingencies", {}),
        "Settings": {
            "darkMode": settings.get("dark_mode", False),
            "notifications": settings.get("notifications", True),
            "autoSave": True,
            "defaultDayType": settings.get("default_day_type", "A"),
        },
        "_identity": {"mission": identity.get("mission", ""), "motto": identity.get("motto", "")},
    }


def merge_blob(current: dict[str, Any] | None, fields: dict[str, Any], reset: bool) -> dict[str, Any]:
    """Overwrite template-controlled keys; preserve runtime data unless --reset."""
    identity = fields.pop("_identity")

    base: dict[str, Any] = {} if (reset or not current) else dict(current)
    base.update(fields)

    # Today holds mission/motto + the per-day journal of priorities.
    today = {} if (reset or not isinstance(base.get("Today"), dict)) else dict(base["Today"])
    today["mission"] = identity["mission"]
    today["motto"] = identity["motto"]
    today.setdefault("daily", {})
    base["Today"] = today

    if reset:
        for key in RUNTIME_KEYS:
            if key == "Today":
                continue
            base[key] = {} if key in ("DayPlans", "_OrchestratorMeta", "WeeklyPlan", "EightSteps") else []
        base["WeeklyPlan"] = {
            "weekOf": "", "primaryLetter": "", "weekCountsIf": "",
            "pigpenFocus": {}, "closed": False,
            "reflection": {"weekRating": 0, "stepsLived": {}, "stepsNotes": {}},
        }

    base.setdefault("version", "2.0")
    base.setdefault("screen", "Home")
    base["onboardingDone"] = True  # profile IS the onboarding — never show the wizard again
    return base


# ------------------------------------------------------------------------ http

def _auth_headers(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def fetch_token(api: str) -> str | None:
    """Fetch the localhost bearer token the same way the browser app does.

    GET /api/auth/token is exempt from auth; returns {"ok": true, "token": <key|null>}.
    null means delta-kernel is in dev mode (no .aegis-tenant-key) and needs no auth.
    """
    url = f"{api.rstrip('/')}/api/auth/token"
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:  # noqa: S310 (localhost)
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("token")


def extract_blob(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Unwrap the cycleboard blob from a GET response.

    The server stores the PUT body at entity.state.data, so GET returns
    {"ok": true, "data": {"data": <blob>}}. The real app state is the inner
    object. A stray top-level 'data' key (from older mis-nested writes) is
    stripped so repeated applies don't accumulate nesting.
    """
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    inner = data.get("data")
    blob = inner if isinstance(inner, dict) else data
    if "data" in blob:  # defensive: drop any stray wrapper key
        blob = {k: v for k, v in blob.items() if k != "data"}
    return blob


def get_current_state(api: str, token: str | None) -> dict[str, Any] | None:
    url = f"{api.rstrip('/')}/api/cycleboard"
    req = urllib.request.Request(url, headers=_auth_headers(token))
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 (localhost)
        payload = json.loads(resp.read().decode("utf-8"))
    return extract_blob(payload)


def put_state(api: str, token: str | None, blob: dict[str, Any]) -> None:
    url = f"{api.rstrip('/')}/api/cycleboard"
    body = json.dumps(blob).encode("utf-8")
    headers = {"Content-Type": "application/json", **_auth_headers(token)}
    req = urllib.request.Request(url, data=body, method="PUT", headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 (localhost)
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(f"hub rejected the write: {payload}")


# ------------------------------------------------------------------------ main

def _summarize(profile: dict[str, Any]) -> str:
    routines = profile.get("routines", {})
    day_types = profile.get("day_types", {})
    r = ", ".join(f"{n}({len(s)})" for n, s in routines.items()) or "none"
    d = ", ".join(f"{k}:{v.get('name', k)}" for k, v in day_types.items()) or "none"
    return f"routines [{r}]  ·  day types [{d}]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fan a behavioral profile out to all Atlas surfaces.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--dry-run", action="store_true", help="Print the resulting blob, do not write.")
    parser.add_argument("--reset", action="store_true", help="Blank canvas: also wipe accumulated runtime data.")
    args = parser.parse_args(argv)

    if not args.profile.exists():
        print(f"[x] profile not found: {args.profile}", file=sys.stderr)
        return 1

    profile = load_profile(args.profile)
    errors = validate_profile(profile)
    if errors:
        print(f"[x] {len(errors)} validation error(s) in {args.profile.name}:", file=sys.stderr)
        for e in errors:
            print(f"    - {e}", file=sys.stderr)
        return 1

    print(f"[*] profile: {args.profile.name}  ·  {_summarize(profile)}")
    fields = build_state_fields(profile)

    if args.dry_run:
        blob = merge_blob(None, fields, reset=args.reset)
        print(json.dumps(blob, indent=2))
        print("\n[i] dry-run: nothing written.")
        return 0

    try:
        token = fetch_token(args.api)
        current = None if args.reset else get_current_state(args.api, token)
    except urllib.error.URLError as e:
        print(f"[x] cannot reach delta-kernel at {args.api} ({e}). Is it running? (start_atlas.ps1)",
              file=sys.stderr)
        return 2

    blob = merge_blob(current, fields, reset=args.reset)

    try:
        put_state(args.api, token, blob)
    except (urllib.error.URLError, RuntimeError) as e:
        print(f"[x] write failed: {e}", file=sys.stderr)
        return 2

    mode = "RESET (blank canvas)" if args.reset else "merged (runtime preserved)"
    print(f"[ok] applied to {args.api}/api/cycleboard  ·  {mode}")
    print("     propagates to: inPACT app + inPACT CLI + cortex cadence + delta-kernel CLIs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
