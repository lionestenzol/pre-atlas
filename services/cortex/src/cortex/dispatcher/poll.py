"""Long-poll the delta-kernel /api/atlas/next-directive endpoint.

Contract: GET /api/atlas/next-directive returns
  - 200 + {ok: True, directive: {...}} when a Directive.v1 is ready
  - 204                                  when the work ledger is empty
  - 500 + {ok: False, error, details}    on schema validation failure

poll_once() does one request and returns the directive dict (200) or
None (204). Other status codes raise via response.raise_for_status().

poll_loop() runs poll_once forever, applying exponential backoff on 204
(no work) and resetting on 200. The on_directive callback handles
routing/execution.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BACKOFF_INITIAL_S = 2.0
DEFAULT_BACKOFF_MAX_S = 30.0


async def poll_once(client: httpx.AsyncClient, base_url: str) -> Optional[dict]:
    """One poll. Returns the directive dict on 200, None on 204.

    Raises:
        httpx.HTTPStatusError: on non-200/non-204 status codes
        ValueError: on 200 response missing the 'directive' key
    """
    url = f"{base_url.rstrip('/')}/api/atlas/next-directive"
    logger.debug("polling %s", url)
    response = await client.get(url)
    if response.status_code == 204:
        return None
    if response.status_code == 200:
        body = response.json()
        if "directive" not in body:
            raise ValueError(f"200 response missing 'directive' key: {body!r}")
        return body["directive"]
    response.raise_for_status()
    return None  # unreachable; raise_for_status() raised


async def poll_loop(
    client: httpx.AsyncClient,
    base_url: str,
    on_directive: Callable[[dict], Awaitable[None]],
    *,
    initial_backoff: float = DEFAULT_BACKOFF_INITIAL_S,
    max_backoff: float = DEFAULT_BACKOFF_MAX_S,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Poll forever.

    On 200 → invoke on_directive then reset backoff.
    On 204 → sleep current backoff, then double up to max_backoff.
    On exception in poll_once → log + back off.
    Exception in on_directive is logged but does not break the loop.

    The sleep parameter is injectable for testability.
    """
    backoff = initial_backoff
    logger.info("dispatcher poll loop starting · base_url=%s", base_url)
    while True:
        try:
            directive = await poll_once(client, base_url)
        except Exception:
            logger.info("poll_once failed · backing off %.1fs", backoff)
            logger.exception("poll_once exception detail")
            await sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
            continue

        if directive is None:
            logger.info("204 no work · backoff %.1fs", backoff)
            await sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
            continue

        if backoff != initial_backoff:
            logger.info("backoff reset on 200 · backoff %.1fs → %.1fs", backoff, initial_backoff)
        backoff = initial_backoff
        directive_id = directive.get("directive_id", "<unknown>")
        logger.info("received directive · directive_id=%s", directive_id)
        try:
            await on_directive(directive)
        except Exception:
            logger.exception("on_directive callback failed for %s", directive_id)
            # Loop continues; do not let a bad directive kill the dispatcher.
