# Atlas Setup — one profile, all surfaces

**The problem this kills:** Atlas has 35+ surfaces, but the *behavioral* ones —
inPACT (app + CLI), cortex's morning/midday/evening cadence, and the delta-kernel
CLIs — each used to need routines and A/B/C day types set up by hand, and they
shipped with **placeholder "bs" data** that looked like it was working but wasn't
yours. This folder makes one file the truth and fans it out everywhere, headlessly.

## The one fact that makes this small

Every behavioral surface reads the **same** state blob: the delta-kernel
cycleboard state at `PUT /api/cycleboard` (port 3001). cortex reads its day-type
templates straight out of that state ([orchestrator.py](../services/cortex/src/cortex/inpact/orchestrator.py#L67-L74)),
the inPACT app syncs to it, the inPACT/atlas CLIs read it. So **one write
propagates to all of them** — no 35 integrations.

```
setup/atlas_profile.json ──(apply.py)──► PUT /api/cycleboard ──► inPACT app
       (the truth)                          (the hub, :3001)   ├─► inPACT CLI
                                                                ├─► cortex cadence (morning/midday/evening)
                                                                └─► delta-kernel CLIs (atlas / atlas-ai)
```

## Files

| File | What it is |
|---|---|
| `atlas_profile.json` | **Your active profile** — the single source of truth. Edit this. |
| `atlas_profile.template.json` | **Blank canvas** — what a brand-new person fills in. Ship this. |
| `atlas_profile.schema.json` | The contract (draft-07 JSON Schema). |
| `apply.py` | Headless fan-out engine (stdlib only — no pip install). |
| `test_apply.py` | `python -m pytest setup/test_apply.py -q` → 18 tests. |
| `setup.ps1` | Turnkey: start all services **then** apply the profile. |

## Daily / common use

```bash
# Edit your life in setup/atlas_profile.json, then:
python setup/apply.py                 # fan out to all surfaces (runtime data preserved)
python setup/apply.py --dry-run        # preview the resulting blob, write nothing
```

`apply.py` is **idempotent** — run it as many times as you want. A normal apply
overwrites only the template-controlled keys (routines, day types, focus areas,
settings, mission/motto) and **preserves** everything you've accumulated
(`DayPlans`, `Journal`, `History`, `MomentumWins`, weekly reflections).

## Re-setup / hand to someone else (blank canvas)

```bash
# Wipe to a blank canvas (also clears accumulated runtime data):
python setup/apply.py --profile setup/atlas_profile.template.json --reset

# A new person: copy the template, fill it, apply it.
cp setup/atlas_profile.template.json setup/atlas_profile.json
#   ...edit atlas_profile.json (mission, routines, day types)...
python setup/apply.py
```

## Fully headless / fresh machine

```powershell
pwsh setup/setup.ps1            # starts services (start_atlas.ps1) then applies the profile
pwsh setup/setup.ps1 -Reset     # same, but blank-canvas the behavioral state first
```

## Profile shape (snake_case in, the app's camelCase generated out)

```jsonc
{
  "identity":   { "mission": "...", "motto": "..." },
  "focus_areas":[ { "name": "Production", "definition": "...", "color": "#3B82F6" } ],
  "routines":   { "Morning": ["step", ...], "Evening": [...] },   // add any custom routine
  "day_types":  {
    "A": { "name": "Optimal Day", "time_blocks": [ {"time":"6:00 AM","title":"...","duration":60} ],
           "routines": ["Morning","Evening"], "goals": {"baseline":"...","stretch":"..."} }
  },
  "settings":   { "default_day_type": "A", "dark_mode": false, "notifications": true },
  "az_tasks":   [],          // optional monthly milestones; empty = blank
  "contingencies": { "lowEnergy": { "enabled": true, "actions": ["..."] } }
}
```

`apply.py` validates the profile before writing (every `day_type.routines` entry
must name a real routine; `default_day_type` must exist; time blocks need a time +
title). Validation failure = non-zero exit, nothing written.

## Auth note

delta-kernel guards `/api/*` with a Bearer key from `.aegis-tenant-key`. `apply.py`
fetches that token the same way the browser does (`GET /api/auth/token`, which is
exempt) and uses it automatically. If there's no key file (dev mode), it just works.
