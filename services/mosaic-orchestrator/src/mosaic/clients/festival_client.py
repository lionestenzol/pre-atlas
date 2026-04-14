"""Festival client — wraps WSL2 CLI commands for festival methodology.

All fest commands run via: wsl -d Ubuntu -- bash -c "cd /root/festival-project && fest <cmd>"
"""
import asyncio
import json
import structlog
from typing import Any

log = structlog.get_logger()

FEST_TIMEOUT = 30  # seconds
FEST_BASE = "cd /root/festival-project && fest"


class FestivalClient:
    """WSL2 subprocess-based client for festival methodology."""

    async def _run(self, fest_cmd: str) -> tuple[int, str, str]:
        """Run a fest command via WSL2."""
        full_cmd = f'wsl -d Ubuntu -- bash -c "{FEST_BASE} {fest_cmd}"'
        log.info("festival_client.run", command=fest_cmd)

        try:
            proc = await asyncio.create_subprocess_shell(
                full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=FEST_TIMEOUT
            )
            return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            log.error("festival_client.timeout", command=fest_cmd, timeout=FEST_TIMEOUT)
            proc.kill()
            return -1, "", f"Timeout after {FEST_TIMEOUT}s"

    async def status(self) -> dict[str, Any]:
        """Get current festival status."""
        rc, stdout, stderr = await self._run("status")
        return {"success": rc == 0, "output": stdout.strip(), "error": stderr.strip()}

    async def progress(self) -> dict[str, Any]:
        """Get festival completion progress."""
        rc, stdout, stderr = await self._run("progress")
        return {"success": rc == 0, "output": stdout.strip(), "error": stderr.strip()}

    async def next_task(self) -> dict[str, Any]:
        """Find next task to work on."""
        rc, stdout, stderr = await self._run("next")
        return {"success": rc == 0, "output": stdout.strip(), "error": stderr.strip()}

    async def complete_task(self, task_id: str = "") -> dict[str, Any]:
        """Mark current or specified task as complete."""
        cmd = f"task complete {task_id}".strip()
        rc, stdout, stderr = await self._run(cmd)
        return {"success": rc == 0, "output": stdout.strip(), "error": stderr.strip()}

    async def list_festivals(self) -> dict[str, Any]:
        """List all festivals."""
        rc, stdout, stderr = await self._run("list")
        return {"success": rc == 0, "output": stdout.strip(), "error": stderr.strip()}
