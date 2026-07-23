"""Tests for openclaw.config."""
from openclaw.config import OpenClawConfig


class TestOpenClawConfig:
    def test_defaults(self):
        cfg = OpenClawConfig()
        assert cfg.port == 3004
        # mosaic-orchestrator (:3005) + mirofish (:3003) retired (FA0001); status now
        # reads delta-kernel directly.
        assert cfg.delta_url == "http://localhost:3001"
        assert cfg.brief_cron_hour == 9
        assert cfg.brief_cron_minute == 30
        assert cfg.stall_threshold_hours == 48
        assert cfg.slack_channel == "#atlas-briefs"
