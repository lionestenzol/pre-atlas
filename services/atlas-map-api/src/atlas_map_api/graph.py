"""In-memory graph queries over the service_edges from atlas-map.json.

Uses stdlib BFS — the graph is ~33 nodes, ~20 edges. networkx would be overkill.
Direction-aware: an edge a→b means "a depends on b" (a imports b).
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable


class ServiceGraph:
    def __init__(self, edges: Iterable[tuple[str, str]], nodes: Iterable[str] = ()):
        self._out: dict[str, set[str]] = defaultdict(set)
        self._in: dict[str, set[str]] = defaultdict(set)
        self._nodes: set[str] = set(nodes)
        for a, b in edges:
            self._out[a].add(b)
            self._in[b].add(a)
            self._nodes.add(a)
            self._nodes.add(b)

    @property
    def nodes(self) -> list[str]:
        return sorted(self._nodes)

    def neighbors_out(self, name: str) -> list[str]:
        return sorted(self._out.get(name, ()))

    def neighbors_in(self, name: str) -> list[str]:
        return sorted(self._in.get(name, ()))

    def neighborhood(self, name: str, hops: int = 1) -> dict[str, list[str]]:
        """Return all nodes within `hops` of `name`, grouped by distance.

        Distance is the minimum hops in either direction (undirected for reach,
        but the per-edge direction is preserved in out/in queries).
        """
        if name not in self._nodes:
            return {}
        seen: dict[str, int] = {name: 0}
        q: deque[tuple[str, int]] = deque([(name, 0)])
        while q:
            cur, dist = q.popleft()
            if dist >= hops:
                continue
            for nb in (self._out.get(cur, set()) | self._in.get(cur, set())):
                if nb not in seen:
                    seen[nb] = dist + 1
                    q.append((nb, dist + 1))
        out: dict[str, list[str]] = defaultdict(list)
        for n, d in seen.items():
            out[str(d)].append(n)
        for k in out:
            out[k].sort()
        return dict(out)

    def shortest_path(self, src: str, dst: str) -> list[str] | None:
        """BFS shortest path src→dst, following the directed edges.

        Returns the list of node names (inclusive of both endpoints), or None
        if no directed path exists. For undirected reachability, call twice and
        take the shorter, or use neighborhood().
        """
        if src not in self._nodes or dst not in self._nodes:
            return None
        if src == dst:
            return [src]
        prev: dict[str, str] = {src: src}
        q: deque[str] = deque([src])
        while q:
            cur = q.popleft()
            for nb in self._out.get(cur, set()):
                if nb in prev:
                    continue
                prev[nb] = cur
                if nb == dst:
                    path = [nb]
                    while path[-1] != src:
                        path.append(prev[path[-1]])
                    return list(reversed(path))
                q.append(nb)
        return None
