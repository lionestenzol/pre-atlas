import pytest

from habit_tracker import update_habit, run_check_in, COMPLETED, PARTIAL, SKIPPED

XP_VALUES = {
    "Wake Up & Hydrate": 5,
    "Voice Journaling": 10,
    "Deep Work": 20,
}


def test_completed_adds_xp_and_increments_streak():
    state = {"xp": 0, "streak": 3}
    result = update_habit(state, COMPLETED, 5)
    assert result == {"xp": 5, "streak": 4}


def test_partial_adds_half_xp_streak_unchanged():
    state = {"xp": 0, "streak": 3}
    result = update_habit(state, PARTIAL, 10)
    assert result == {"xp": 5, "streak": 3}


def test_skipped_subtracts_xp_and_resets_streak():
    state = {"xp": 20, "streak": 3}
    result = update_habit(state, SKIPPED, 5)
    assert result == {"xp": 15, "streak": 0}


def test_unknown_status_raises():
    with pytest.raises(ValueError):
        update_habit({"xp": 0, "streak": 0}, "Bogus", 5)


def test_run_check_in_applies_across_habits():
    states = {
        "Wake Up & Hydrate": {"xp": 0, "streak": 2},
        "Voice Journaling": {"xp": 0, "streak": 0},
        "Deep Work": {"xp": 0, "streak": 1},
    }
    day_log = {
        "Wake Up & Hydrate": COMPLETED,
        "Voice Journaling": SKIPPED,
        "Deep Work": PARTIAL,
    }
    updated = run_check_in(states, XP_VALUES, day_log)

    assert updated["Wake Up & Hydrate"] == {"xp": 5, "streak": 3}
    assert updated["Voice Journaling"] == {"xp": -10, "streak": 0}
    assert updated["Deep Work"] == {"xp": 10, "streak": 1}


def test_run_check_in_leaves_unlogged_habits_unchanged():
    states = {"Wake Up & Hydrate": {"xp": 5, "streak": 1}}
    updated = run_check_in(states, XP_VALUES, {})
    assert updated["Wake Up & Hydrate"] == {"xp": 5, "streak": 1}


def test_multi_day_streak_accumulates():
    state = {"xp": 0, "streak": 0}
    for _ in range(5):
        state = update_habit(state, COMPLETED, 5)
    assert state == {"xp": 25, "streak": 5}
