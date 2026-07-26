"""Local code search — shells out to the DropList Search Tightening Protocol ladder.

For kind=code queries, this provider runs the appropriate tool based on the
prefix operator (rg:/fd:/sg:) or falls back to rg as the default.
"""

from __future__ import annotations

import asyncio
import shutil

from .base import SearchProvider, SearchResult


class RepoSearchProvider(SearchProvider):
    name = "repo_search"
    kind_default = "code"

    def _check_enabled(self) -> bool:
        return shutil.which("rg") is not None

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        if query.startswith("rg:"):
            return await self._rg(query[3:].strip(), max_results)
        if query.startswith("fd:"):
            return await self._fd(query[3:].strip(), max_results)
        if query.startswith("sg:"):
            return await self._sg(query[3:].strip(), max_results)
        return await self._rg(query, max_results)

    async def _rg(self, pattern: str, max_results: int) -> list[SearchResult]:
        # `--` end-of-options: `pattern` is unauthenticated request input (POST /search
        # {"q": "rg:<pattern>"}) — without it, a pattern like "--files" is parsed by
        # rg's own arg parser as a flag, turning a text-search endpoint into
        # unauthenticated filesystem enumeration. Same CVE-2017-1000117-shaped class as
        # the git clone fix earlier in this sweep. See ~/.claude/rules/common/code-as-furniture.md.
        cmd = ["rg", "-n", "--max-count", str(max_results), "--json", "--", pattern]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        out: list[SearchResult] = []
        import json

        for line in stdout.decode("utf-8", errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except Exception:
                continue
            if entry.get("type") != "match":
                continue
            d = entry.get("data", {})
            path = (d.get("path") or {}).get("text", "")
            line_num = d.get("line_number", 0)
            text = (d.get("lines") or {}).get("text", "").rstrip()
            out.append(
                SearchResult(
                    title=f"{path}:{line_num}",
                    url=f"file://{path}#L{line_num}",
                    snippet=text[:500],
                    score=1.0,
                    source="rg",
                    kind="code",
                    raw={"path": path, "line": line_num},
                )
            )
            if len(out) >= max_results:
                break
        return out

    async def _fd(self, pattern: str, max_results: int) -> list[SearchResult]:
        # See _rg's comment — same positional-arg-injection guard (e.g. "-uu" would
        # otherwise bypass .gitignore excludes and enumerate hidden/ignored files).
        cmd = ["fd", "--max-results", str(max_results), "--", pattern]
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
                    title=path,
                    url=f"file://{path}",
                    snippet="",
                    score=1.0,
                    source="fd",
                    kind="code",
                    raw={"path": path},
                )
            )
        return out

    async def _sg(self, pattern: str, max_results: int) -> list[SearchResult]:
        if shutil.which("sg") is None:
            return []
        cmd = ["sg", "--pattern", pattern, "--json"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        out: list[SearchResult] = []
        import json

        try:
            entries = json.loads(stdout.decode("utf-8", errors="replace") or "[]")
        except Exception:
            entries = []
        for entry in entries[:max_results]:
            path = entry.get("file", "")
            line_num = entry.get("range", {}).get("start", {}).get("line", 0)
            text = entry.get("text", "")
            out.append(
                SearchResult(
                    title=f"{path}:{line_num}",
                    url=f"file://{path}#L{line_num}",
                    snippet=text[:500],
                    score=1.0,
                    source="sg",
                    kind="code",
                    raw={"path": path, "line": line_num},
                )
            )
        return out
