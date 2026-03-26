"""Tests for mosaic workflow modules."""
import pytest
from mosaic.workflows.daily_loop import run_daily_loop
from mosaic.workflows.stall_detector import detect_stalls
from mosaic.workflows.idea_simulation import run_idea_to_simulation, find_eligible_ideas


@pytest.mark.asyncio
async def test_daily_loop_runs_all_steps(mock_delta, mock_cognitive):
    """Daily loop should execute all steps and return summary."""
    result = await run_daily_loop(mock_delta, mock_cognitive)
    assert result["skipped"] is False
    assert "steps" in result
    assert result["completed"] is not None
    # Should have checked daemon, run daily, pushed to delta, read state
    step_names = [s["step"] for s in result["steps"]]
    assert "check_daemon" in step_names
    assert "cognitive_daily" in step_names


@pytest.mark.asyncio
async def test_daily_loop_skips_when_refreshing(mock_delta, mock_cognitive):
    """Daily loop should skip when daemon is already refreshing."""
    mock_delta.get_daemon_status.return_value = {"refreshing": True}
    result = await run_daily_loop(mock_delta, mock_cognitive)
    assert result["skipped"] is True


@pytest.mark.asyncio
async def test_stall_detector_detects_zero_completions(mock_cognitive, mock_openclaw):
    """Stall detector should trigger on closed_week == 0."""
    result = await detect_stalls(mock_cognitive, mock_openclaw)
    assert result["stall_detected"] is True
    assert len(result["cut_list"]) > 0
    assert result["notified"] is True
    mock_openclaw.notify.assert_called_once()


@pytest.mark.asyncio
async def test_stall_detector_no_stall(mock_cognitive, mock_openclaw, tmp_sensor_dir):
    """Stall detector should not trigger when tasks are being closed."""
    # Override completion_stats with non-zero closed_week
    (tmp_sensor_dir / "completion_stats.json").write_text(
        '{"closed_week": 3, "archived_week": 1, "closed_life": 10, "archived_life": 20, "closure_ratio": 33.3}'
    )
    (tmp_sensor_dir / "daily_payload.json").write_text(
        '{"mode": "BUILD", "closed_week": 3}'
    )
    result = await detect_stalls(mock_cognitive, mock_openclaw)
    # Should not stall because we read completion_stats.json with closed_week=3
    # Note: detect_stalls reads daily_payload first, which has closed_week=3
    assert result["stall_detected"] is False


@pytest.mark.asyncio
async def test_find_eligible_ideas(mock_cognitive):
    """Should find ideas with alignment > 0.7."""
    eligible = await find_eligible_ideas(mock_cognitive)
    assert len(eligible) == 2  # canon_001 (0.85) and canon_003 (0.75)
    ids = [e["canonical_id"] for e in eligible]
    assert "canon_001" in ids
    assert "canon_003" in ids
    assert "canon_002" not in ids  # alignment 0.3 < 0.7


@pytest.mark.asyncio
async def test_idea_to_simulation_routes_by_confidence(mock_cognitive, mock_mirofish, mock_openclaw):
    """Idea simulation should start sims and route by confidence."""
    result = await run_idea_to_simulation(mock_cognitive, mock_mirofish, mock_openclaw)
    assert result["simulations_started"] == 2  # 2 eligible ideas
    assert len(result["routing_decisions"]) == 2
    # Default mock confidence is 0.85 → create_festival_task
    for decision in result["routing_decisions"]:
        assert decision["action"] == "create_festival_task"


@pytest.mark.asyncio
async def test_idea_simulation_moderate_confidence(mock_cognitive, mock_mirofish, mock_openclaw):
    """Moderate confidence should trigger OpenClaw notification."""
    mock_mirofish.get_report.return_value = {"confidence": 0.6}
    result = await run_idea_to_simulation(mock_cognitive, mock_mirofish, mock_openclaw)
    for decision in result["routing_decisions"]:
        assert decision["action"] == "notify_for_review"
    assert mock_openclaw.notify.call_count == 2  # one per eligible idea


@pytest.mark.asyncio
async def test_idea_simulation_low_confidence(mock_cognitive, mock_mirofish, mock_openclaw):
    """Low confidence should archive without notification."""
    mock_mirofish.get_report.return_value = {"confidence": 0.3}
    result = await run_idea_to_simulation(mock_cognitive, mock_mirofish, mock_openclaw)
    for decision in result["routing_decisions"]:
        assert decision["action"] == "archive"
    mock_openclaw.notify.assert_not_called()
