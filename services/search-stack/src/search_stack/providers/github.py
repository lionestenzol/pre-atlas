"""GitHub search via gh CLI passthrough.

Uses `gh search code|repos|issues` depending on intent. No GitHub token required
beyond what `gh auth login` already set up.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from .base import SearchProvider, SearchResult


class GitHubProvider(SearchProvider):
    name = "github"
    kind_default = "github"

    def _check_enabled(self) -> bool:
        return shutil.which("gh") is not None

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        q = query.strip()
        if q.lower().startswith("repo:"):
            q = q[5:].strip()
            return await self._gh_repos(q, max_results)
        if "site:github.com" in q.lower():
            q = q.lower().replace("site:github.com", "").strip()
            return await self._gh_code(q, max_results)
        return await self._gh_code(q, max_results)

    async def _gh_code(self, query: str, max_results: int) -> list[SearchResult]:
        cmd = [
            "gh",
            "search",
            "code",
            query,
            "--limit",
            str(max_results),
            "--json",
            "path,repository,url,textMatches",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"gh search code failed: {stderr.decode()[:200]}")

        try:
            entries = json.loads(stdout.decode("utf-8") or "[]")
        except Exception:
            entries = []

        out: list[SearchResult] = []
        for entry in entries:
            repo = entry.get("repository", {})
            repo_name = repo.get("nameWithOwner") or repo.get("name", "")
            path = entry.get("path", "")
            url = entry.get("url", "")
            matches = entry.get("textMatches") or []
            snippet = matches[0].get("fragment", "") if matches else ""
            out.append(
                SearchResult(
                    title=f"{repo_name}/{path}",
                    url=url,
                    snippet=snippet[:500],
                    score=1.0,
                    source="gh-code",
                    kind="github",
                    raw={"repo": repo_name, "path": path},
                )
            )
        return out

    async def _gh_repos(self, query: str, max_results: int) -> list[SearchResult]:
        cmd = [
            "gh",
            "search",
            "repos",
            query,
            "--limit",
            str(max_results),
            "--json",
            "fullName,description,url,stargazersCount,updatedAt",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"gh search repos failed: {stderr.decode()[:200]}")

        try:
            entries = json.loads(stdout.decode("utf-8") or "[]")
        except Exception:
            entries = []

        out: list[SearchResult] = []
        for entry in entries:
            stars = entry.get("stargazersCount", 0)
            out.append(
                SearchResult(
                    title=entry.get("fullName", ""),
                    url=entry.get("url", ""),
                    snippet=entry.get("description", "") or "",
                    score=min(1.0, stars / 10000),
                    source="gh-repos",
                    kind="github",
                    raw={"stars": stars, "updated_at": entry.get("updatedAt")},
                )
            )
        return out
