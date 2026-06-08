"""Local file search — wraps Everything CLI (es) for machine-wide lookups.

Query format: prefix `path:` or `file:` is stripped; rest is passed to es.
"""

from __future__ import annotations

import asyncio
import shutil

from .base import SearchProvider, SearchResult


class LocalFileProvider(SearchProvider):
    name = "local_file"
    kind_default = "file"

    def _check_enabled(self) -> bool:
        return shutil.which("es") is not None

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        q = query
        if q.startswith("path:") or q.startswith("file:"):
            q = q.split(":", 1)[1].strip()

        cmd = ["es", "-n", str(max_results), "-p", q]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        out: list[SearchResult] = []
        for path in stdout.decode("utf-8", errors="replace").splitlines():
            path = path.strip()
            if not path:
                continue
            out.append(
                SearchResult(
                    title=path.split("\\")[-1].split("/")[-1] or path,
                    url=f"file:///{path.replace(chr(92), '/')}",
                    snippet=path,
                    score=1.0,
                    source="es",
                    kind="file",
                    raw={"path": path},
                )
            )
        return out
