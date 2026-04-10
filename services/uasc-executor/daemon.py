#!/usr/bin/env python3
"""
Atlas Execution Daemon

Autonomous execution layer for Atlas:
- polls delta-kernel for approved executable work
- claims one task at a time
- executes through the UASC executor
- retries transient failures
- logs final outcome back into delta
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Optional


DELTA_URL = os.environ.get("ATLAS_DELTA_URL", "http://localhost:3001")
UASC_URL = os.environ.get("ATLAS_UASC_URL", "http://localhost:3008")
EXECUTOR_ID = os.environ.get("ATLAS_EXECUTOR_ID", "atlas-execution-daemon")
DELTA_POLL_INTERVAL_S = int(os.environ.get("ATLAS_DAEMON_POLL_INTERVAL_S", "5"))
DELTA_REQUEST_TIMEOUT_S = int(os.environ.get("ATLAS_DELTA_TIMEOUT_S", "15"))
UASC_REQUEST_TIMEOUT_S = int(os.environ.get("ATLAS_UASC_TIMEOUT_S", "120"))
MAX_RETRIES = int(os.environ.get("ATLAS_DAEMON_MAX_RETRIES", "3"))
RETRY_DELAY_S = int(os.environ.get("ATLAS_DAEMON_RETRY_DELAY_S", "5"))
UASC_CLIENT_ID = os.environ.get("ATLAS_UASC_CLIENT_ID", "atlas-execution-daemon")
UASC_SECRET = os.environ.get("ATLAS_UASC_SECRET", "atlas-execution-daemon-local-secret")


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def sleep_with_shutdown(seconds: int) -> None:
    if seconds > 0:
        time.sleep(seconds)


class DeltaClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._token: Optional[str] = None

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
        include_auth: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}

        if include_auth:
            token = self.get_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        with urllib.request.urlopen(request, timeout=DELTA_REQUEST_TIMEOUT_S) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    def get_token(self) -> Optional[str]:
        if self._token is not None:
            return self._token

        response = self._request("GET", "/api/auth/token", include_auth=False)
        self._token = response.get("token")
        return self._token

    def claim_next_task(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/work/claim",
            payload={"executor_id": EXECUTOR_ID},
        )

    def complete_task(
        self,
        job_id: str,
        outcome: str,
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": job_id,
            "outcome": outcome,
        }
        if result is not None:
            payload["result"] = result
        if error:
            payload["error"] = error
        if metrics:
            payload["metrics"] = metrics
        return self._request("POST", "/api/work/complete", payload=payload)


class UASCClient:
    def __init__(self, base_url: str, client_id: str, secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.secret = secret

    def _signature(self, timestamp: str, body: str) -> str:
        message = f"{timestamp}{body}".encode("utf-8")
        return hmac.new(self.secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    def execute(self, cmd: str, inputs: dict[str, Any]) -> dict[str, Any]:
        payload = {"cmd": cmd, **inputs}
        body = json.dumps(payload)
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-UASC-Client": self.client_id,
            "X-UASC-Timestamp": timestamp,
            "X-UASC-Signature": self._signature(timestamp, body),
        }
        request = urllib.request.Request(
            f"{self.base_url}/exec",
            data=body.encode("utf-8"),
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=UASC_REQUEST_TIMEOUT_S) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}


class AtlasExecutionDaemon:
    def __init__(self) -> None:
        self.delta = DeltaClient(DELTA_URL)
        self.uasc = UASCClient(UASC_URL, UASC_CLIENT_ID, UASC_SECRET)

    def run_forever(self) -> None:
        print(f"[{utc_now()}] atlas-execution-daemon started")
        print(f"[{utc_now()}] delta={DELTA_URL} uasc={UASC_URL} executor_id={EXECUTOR_ID}")

        while True:
            try:
                claim = self.delta.claim_next_task()
                if not claim.get("claimed"):
                    sleep_with_shutdown(DELTA_POLL_INTERVAL_S)
                    continue

                job = claim.get("job") or {}
                self.execute_claimed_job(job)
            except KeyboardInterrupt:
                print(f"[{utc_now()}] atlas-execution-daemon stopping")
                raise
            except Exception as exc:
                print(f"[{utc_now()}] daemon loop error: {exc}")
                sleep_with_shutdown(DELTA_POLL_INTERVAL_S)

    def execute_claimed_job(self, job: dict[str, Any]) -> None:
        job_id = str(job.get("job_id", ""))
        title = str(job.get("title", "untitled"))
        metadata = job.get("metadata") or {}

        if not isinstance(metadata, dict):
            self.log_failure(job_id, title, "Invalid task metadata")
            return

        cmd = metadata.get("cmd")
        if not isinstance(cmd, str) or not cmd.strip():
            self.log_failure(job_id, title, "Missing metadata.cmd")
            return

        raw_inputs = metadata.get("inputs") or {}
        if not isinstance(raw_inputs, dict):
            self.log_failure(job_id, title, "metadata.inputs must be an object")
            return

        inputs = dict(raw_inputs)
        started_at = time.time()
        last_error: Optional[str] = None

        print(f"[{utc_now()}] claimed job={job_id} title={title} cmd={cmd}")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = self.uasc.execute(cmd, inputs)
                duration_ms = int((time.time() - started_at) * 1000)
                self.delta.complete_task(
                    job_id=job_id,
                    outcome="completed",
                    result={
                        "executor": EXECUTOR_ID,
                        "attempts": attempt,
                        "cmd": cmd,
                        "uasc_run_id": result.get("run_id"),
                        "uasc_status": result.get("status"),
                        "steps": result.get("steps", []),
                        "outputs": result.get("outputs", {}),
                        "completed_at": utc_now(),
                    },
                    metrics={"duration_ms": duration_ms},
                )
                print(f"[{utc_now()}] completed job={job_id} attempt={attempt}")
                return
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code}: {detail or exc.reason}"
            except urllib.error.URLError as exc:
                last_error = f"Connection error: {exc.reason}"
            except Exception as exc:
                last_error = str(exc)

            print(f"[{utc_now()}] attempt={attempt} failed job={job_id}: {last_error}")

            if attempt < MAX_RETRIES:
                sleep_with_shutdown(RETRY_DELAY_S)

        duration_ms = int((time.time() - started_at) * 1000)
        self.delta.complete_task(
            job_id=job_id,
            outcome="failed",
            result={
                "executor": EXECUTOR_ID,
                "attempts": MAX_RETRIES,
                "cmd": cmd,
                "completed_at": utc_now(),
            },
            error=last_error or "Execution failed",
            metrics={"duration_ms": duration_ms},
        )
        print(f"[{utc_now()}] failed job={job_id} after {MAX_RETRIES} attempts")

    def log_failure(self, job_id: str, title: str, error: str) -> None:
        print(f"[{utc_now()}] invalid executable job={job_id} title={title}: {error}")
        self.delta.complete_task(
            job_id=job_id,
            outcome="failed",
            result={"executor": EXECUTOR_ID, "completed_at": utc_now()},
            error=error,
            metrics={"duration_ms": 0},
        )


def main() -> None:
    daemon = AtlasExecutionDaemon()
    daemon.run_forever()


if __name__ == "__main__":
    main()
