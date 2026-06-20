"""Smoke tests for atlas CLI — exercises typer commands against the live API.

These tests REQUIRE atlas-map-api running on :3072. Skip cleanly when it isn't.
"""

from __future__ import annotations

import json
import os
import socket

import pytest
from typer.testing import CliRunner

from atlas_cli.client import find_repo_root, to_repo_relative
from atlas_cli.main import app


def _api_up() -> bool:
    base = os.environ.get("ATLAS_API_URL", "http://127.0.0.1:3072")
    host, port = "127.0.0.1", 3072
    if base.startswith("http://"):
        rest = base[len("http://"):]
        if ":" in rest:
            h, p = rest.split(":", 1)
            host = h
            try:
                port = int(p.split("/")[0])
            except ValueError:
                pass
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _api_up(), reason="atlas-map-api not reachable on :3072")

runner = CliRunner()


def test_repo_root_detected():
    root = find_repo_root()
    assert root is not None, "repo root should be detected from the test cwd"
    assert (root / "audit" / "system-index.json").is_file()


def test_to_repo_relative_normalizes_separators():
    rel = to_repo_relative("services/delta-kernel/src/api/server.ts")
    assert "/" in rel
    assert "\\" not in rel


def test_search_json():
    result = runner.invoke(app, ["--json", "search", "delta"])
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    names = [it["name"] for it in body["items"]]
    assert "delta-kernel" in names


def test_status_pretty():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "delta-kernel" in result.output


def test_show_json():
    result = runner.invoke(app, ["--json", "show", "delta-kernel"])
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert body["name"] == "delta-kernel"


def test_path_json():
    result = runner.invoke(app, ["--json", "path", "lattice", "delta-kernel"])
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert body["forward"] == ["lattice", "delta-kernel"]


def test_locate_known():
    result = runner.invoke(app, ["--json", "locate", "services/delta-kernel/src/api/server.ts"])
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert body["system"] == "delta-kernel"


def test_neighbors_json():
    result = runner.invoke(app, ["--json", "neighbors", "delta-kernel", "--hops", "2"])
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert body["root"] == "delta-kernel"
    assert body["hops"] == 2


def test_list_filtered_by_group():
    result = runner.invoke(app, ["--json", "list", "--group", "services"])
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert all(it["group"] == "services" for it in body["items"])


def test_unknown_subsystem_exits_nonzero():
    result = runner.invoke(app, ["show", "__definitely_not_a_real_system__"])
    assert result.exit_code != 0


def test_where_from_service_dir(monkeypatch, tmp_path):
    """`atlas where` should identify the subsystem owning cwd."""
    from atlas_cli.client import find_repo_root
    import os

    repo = find_repo_root()
    assert repo is not None
    target = repo / "services" / "delta-kernel" / "src"
    if not target.is_dir():
        pytest.skip("delta-kernel/src not present in checkout")
    monkeypatch.chdir(target)
    result = runner.invoke(app, ["--json", "where"])
    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert body["system"] == "delta-kernel", body
