"""Tests for the Atlas profile fan-out engine (setup/apply.py).

Pure-function coverage: validation, snake->camel mapping, merge-preserve, reset.
No network — get/put are exercised separately when delta-kernel is live.

Run:  python -m pytest setup/test_apply.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import apply  # noqa: E402  (same-dir module; pytest adds setup/ to sys.path via rootdir)

HERE = Path(__file__).resolve().parent


# ------------------------------------------------------------------- fixtures

@pytest.fixture
def good_profile() -> dict:
    return {
        "identity": {"mission": "ship", "motto": "keep going"},
        "focus_areas": [{"name": "Production", "definition": "output", "color": "#3B82F6"}],
        "routines": {"Morning": ["Hydrate", "Stretch"], "Evening": ["Tidy"]},
        "day_types": {
            "A": {
                "name": "Optimal Day",
                "description": "full energy",
                "time_blocks": [{"time": "6:00 AM", "title": "Morning Routine", "duration": 60}],
                "routines": ["Morning", "Evening"],
                "goals": {"baseline": "4 blocks", "stretch": "clear inbox"},
            }
        },
        "settings": {"default_day_type": "A", "dark_mode": False, "notifications": True},
        "az_tasks": [],
        "contingencies": {"lowEnergy": {"enabled": True, "actions": ["B-Day"]}},
    }


# ------------------------------------------------------------------ validation

def test_valid_profile_has_no_errors(good_profile):
    assert apply.validate_profile(good_profile) == []


def test_missing_identity_flagged():
    errors = apply.validate_profile({"routines": {}, "day_types": {"A": {"name": "x"}}})
    assert any("identity" in e for e in errors)


def test_day_type_referencing_unknown_routine_flagged(good_profile):
    good_profile["day_types"]["A"]["routines"] = ["Nonexistent"]
    errors = apply.validate_profile(good_profile)
    assert any("not defined in routines" in e for e in errors)


def test_default_day_type_must_exist(good_profile):
    good_profile["settings"]["default_day_type"] = "Z"
    errors = apply.validate_profile(good_profile)
    assert any("default_day_type" in e for e in errors)


def test_empty_day_types_flagged(good_profile):
    good_profile["day_types"] = {}
    errors = apply.validate_profile(good_profile)
    assert any("day_types" in e for e in errors)


def test_time_block_needs_time_and_title(good_profile):
    good_profile["day_types"]["A"]["time_blocks"] = [{"title": "no time"}]
    errors = apply.validate_profile(good_profile)
    assert any("time_blocks" in e for e in errors)


# ----------------------------------------------------------------- build_state

def test_build_maps_snake_to_camel(good_profile):
    fields = apply.build_state_fields(good_profile)
    assert "DayTypeTemplates" in fields
    a = fields["DayTypeTemplates"]["A"]
    assert a["timeBlocks"][0]["title"] == "Morning Routine"  # snake time_blocks -> camel timeBlocks
    assert a["goals"]["baseline"] == "4 blocks"


def test_build_settings_camelcased(good_profile):
    fields = apply.build_state_fields(good_profile)
    assert fields["Settings"]["defaultDayType"] == "A"
    assert fields["Settings"]["darkMode"] is False


def test_build_focus_areas_get_ids(good_profile):
    fields = apply.build_state_fields(good_profile)
    assert fields["FocusArea"][0]["id"] == "fa1"
    assert fields["FocusArea"][0]["tasks"] == []


def test_build_az_tasks_seeded():
    profile = {
        "identity": {"mission": "", "motto": ""},
        "routines": {"Morning": []},
        "day_types": {"A": {"name": "A", "routines": ["Morning"]}},
        "settings": {"default_day_type": "A"},
        "az_tasks": [{"letter": "A", "task": "Define focus"}],
    }
    fields = apply.build_state_fields(profile)
    assert fields["AZTask"][0]["letter"] == "A"
    assert fields["AZTask"][0]["status"] == "Not Started"


# ----------------------------------------------------------------------- merge

def test_merge_preserves_runtime_data(good_profile):
    current = {
        "DayPlans": {"2026-06-25": {"day_type": "A"}},
        "Journal": [{"id": "j1", "text": "yesterday"}],
        "Routine": {"Old": ["stale"]},
    }
    fields = apply.build_state_fields(good_profile)
    blob = apply.merge_blob(current, fields, reset=False)
    # runtime preserved
    assert blob["DayPlans"] == {"2026-06-25": {"day_type": "A"}}
    assert blob["Journal"][0]["text"] == "yesterday"
    # template overwritten
    assert "Morning" in blob["Routine"] and "Old" not in blob["Routine"]


def test_merge_sets_mission_and_onboarding(good_profile):
    fields = apply.build_state_fields(good_profile)
    blob = apply.merge_blob(None, fields, reset=False)
    assert blob["Today"]["mission"] == "ship"
    assert blob["Today"]["motto"] == "keep going"
    assert blob["onboardingDone"] is True


def test_reset_wipes_runtime(good_profile):
    current = {
        "DayPlans": {"2026-06-25": {"day_type": "A"}},
        "Journal": [{"id": "j1"}],
        "MomentumWins": [{"id": "w1"}],
    }
    fields = apply.build_state_fields(good_profile)
    blob = apply.merge_blob(current, fields, reset=True)
    assert blob["DayPlans"] == {}
    assert blob["Journal"] == []
    assert blob["MomentumWins"] == []
    assert blob["Today"]["daily"] == {}
    # but template content still applied
    assert "Morning" in blob["Routine"]


# ----------------------------------------------------------- shipped artifacts

def test_template_and_profile_load_and_validate():
    """The blank canvas and the active profile must both be valid out of the box."""
    for name in ("atlas_profile.template.json", "atlas_profile.json"):
        profile = apply.load_profile(HERE / name)
        assert apply.validate_profile(profile) == [], f"{name} failed validation"


def test_loader_strips_comment_keys():
    profile = apply.load_profile(HERE / "atlas_profile.json")
    assert not any(k.startswith("_") for k in profile)


# ------------------------------------------------------------ blob unwrapping

def test_extract_blob_unwraps_server_nesting():
    """Server returns {ok, data: {data: <blob>}} — extract the inner blob."""
    payload = {"ok": True, "data": {"data": {"Routine": {"Morning": []}, "version": "2.0"}}}
    blob = apply.extract_blob(payload)
    assert blob == {"Routine": {"Morning": []}, "version": "2.0"}


def test_extract_blob_strips_stray_wrapper_key():
    """A stray nested 'data' from older mis-writes must not accumulate."""
    payload = {"ok": True, "data": {"data": {"data": {"old": 1}, "Routine": {"Morning": []}}}}
    blob = apply.extract_blob(payload)
    assert "data" not in blob
    assert blob["Routine"] == {"Morning": []}


def test_extract_blob_handles_empty():
    assert apply.extract_blob({"ok": True, "data": None}) is None
