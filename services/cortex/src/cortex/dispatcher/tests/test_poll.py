"""Tests for cortex.dispatcher.poll."""
from __future__ import annotations

import httpx
import pytest

from cortex.dispatcher.poll import poll_once, poll_loop


def _mock_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    """Build a transport that replays the given responses in order."""
    iterator = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        try:
            return next(iterator)
        except StopIteration:
            return httpx.Response(503, json={"error": "test exhausted responses"})

    return httpx.MockTransport(handler)


async def test_poll_once_returns_directive_on_200():
    transport = _mock_transport([
        httpx.Response(
            200,
            json={"ok": True, "directive": {"directive_id": "d1", "task": {"name": "test"}}},
        ),
    ])
    async with httpx.AsyncClient(transport=transport) as client:
        directive = await poll_once(client, "http://localhost:3001")
    assert directive == {"directive_id": "d1", "task": {"name": "test"}}


async def test_poll_once_returns_none_on_204():
    transport = _mock_transport([httpx.Response(204)])
    async with httpx.AsyncClient(transport=transport) as client:
        directive = await poll_once(client, "http://localhost:3001")
    assert directive is None


async def test_poll_once_raises_on_500():
    transport = _mock_transport([httpx.Response(500, json={"ok": False, "error": "bad"})])
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await poll_once(client, "http://localhost:3001")


async def test_poll_once_raises_on_200_missing_directive():
    transport = _mock_transport([httpx.Response(200, json={"ok": True})])
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ValueError, match="missing 'directive'"):
            await poll_once(client, "http://localhost:3001")


async def test_backoff_doubles_on_repeated_204():
    transport = _mock_transport([
        httpx.Response(204),
        httpx.Response(204),
        httpx.Response(204),
    ])
    sleeps: list[float] = []

    class StopLoop(Exception):
        pass

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)
        if len(sleeps) >= 3:
            raise StopLoop()

    async def noop(d: dict) -> None:
        pass  # never called in this test

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(StopLoop):
            await poll_loop(
                client, "http://localhost:3001", noop,
                initial_backoff=2.0, max_backoff=30.0, sleep=fake_sleep,
            )

    assert sleeps == [2.0, 4.0, 8.0]


async def test_backoff_resets_on_200():
    transport = _mock_transport([
        httpx.Response(204),
        httpx.Response(204),
        httpx.Response(200, json={"ok": True, "directive": {"directive_id": "d1"}}),
        httpx.Response(204),
    ])
    sleeps: list[float] = []
    received: list[dict] = []

    class StopLoop(Exception):
        pass

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)
        if len(sleeps) >= 4:
            raise StopLoop()

    async def collect(d: dict) -> None:
        received.append(d)

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(StopLoop):
            await poll_loop(
                client, "http://localhost:3001", collect,
                initial_backoff=2.0, max_backoff=30.0, sleep=fake_sleep,
            )

    # First two 204s → sleeps 2.0, 4.0; then 200 (no sleep, callback runs);
    # then 204 → sleep 2.0 again (backoff reset). Wait, we only see 3 sleeps
    # before exhausting fixture; the 4th sleep would be 2.0. We stop at 4 sleeps,
    # but only 3 responses are mocked, so 4th sleep is from the 503-exhausted
    # response taking the exception branch (sleeps backoff before retry).
    assert sleeps[:3] == [2.0, 4.0, 2.0]
    assert received == [{"directive_id": "d1"}]


async def test_backoff_caps_at_max():
    # Deliberately use a small max_backoff to verify cap behavior.
    transport = _mock_transport([httpx.Response(204)] * 5)
    sleeps: list[float] = []

    class StopLoop(Exception):
        pass

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)
        if len(sleeps) >= 5:
            raise StopLoop()

    async def noop(d: dict) -> None:
        pass

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(StopLoop):
            await poll_loop(
                client, "http://localhost:3001", noop,
                initial_backoff=2.0, max_backoff=8.0, sleep=fake_sleep,
            )

    # 2.0 → 4.0 → 8.0 → 8.0 (capped) → 8.0 (capped)
    assert sleeps == [2.0, 4.0, 8.0, 8.0, 8.0]


async def test_callback_exception_does_not_break_loop():
    transport = _mock_transport([
        httpx.Response(200, json={"ok": True, "directive": {"directive_id": "d1"}}),
        httpx.Response(200, json={"ok": True, "directive": {"directive_id": "d2"}}),
    ])
    received: list[str] = []

    class StopLoop(Exception):
        pass

    call_count = 0

    async def flaky_callback(d: dict) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("synthetic callback failure")
        received.append(d["directive_id"])
        if call_count >= 2:
            raise StopLoop()

    async def fake_sleep(s: float) -> None:
        pass

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(StopLoop):
            await poll_loop(client, "http://localhost:3001", flaky_callback, sleep=fake_sleep)

    # Loop survived the first failed callback and processed the second directive.
    assert received == ["d2"]
    assert call_count == 2
