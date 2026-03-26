"""Tests for openclaw.config."""
from openclaw.config import OpenClawConfig


class TestOpenClawConfig:
    def test_defaults(self):
        cfg = OpenClawConfig()
        assert cfg.port == 3004
        assert cfg.orchestrator_url == "http://localhost:3005"
        assert cfg.mirofish_url == "http://localhost:3003"
        assert cfg.brief_cron_hour == 9
        assert cfg.brief_cron_minute == 30
        assert cfg.stall_threshold_hours == 48
        assert cfg.slack_channel == "#atlas-briefs"
