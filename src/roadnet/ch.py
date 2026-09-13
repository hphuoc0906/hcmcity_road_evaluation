"""Contraction Hierarchies: preprocessing and bidirectional query."""

from __future__ import annotations

import math
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from heapq import heappop, heappush

import networkx as nx

NO_SHORTCUT = -1
NO_PARENT = -1


@dataclass(slots=True)
class SearchResult:
    """One directed upward Dijkstra run, with the bookkeeping Brandes needs."""

    source: int
    dist: dict[int, float]
    parent: dict[int, int]
    path_counts: dict[int, int]
    settled: list[int]
    predecessors: dict[int, list[int]]


@dataclass(slots=True)
class QueryResult:
    source: int
    target: int
    length: float
    nodes: list[int]
    latency_s: float


@dataclass(slots=True)
class ContractionHierarchies:
    """Contraction Hierarchies over a road graph.

    Node labels must be the integers ``0..n-1`` (see
    :func:`roadnet.data.preprocess.preprocess_graph`, which reindexes them);
    the contraction bookkeeping uses them as array positions.
    """

    graph: nx.MultiDiGraph
    max_hops: int = 5
    theta: int = 50
    unpack_cache_size: int = 500_000

    n: int = field(init=False)
    rank: list[int] = field(init=False)
    weight: dict[int, dict[int, float]] = field(init=False)
    weight_backward: dict[int, dict[int, float]] = field(init=False)
    shortcut: dict[int, dict[int, int]] = field(init=False)
    _work: nx.DiGraph = field(init=False, repr=False)
    _contracted_edges: list[tuple[int, int, float, int]] = field(init=False, repr=False)
    _needs_recompute: list[bool] = field(init=False, repr=False)
    _unpack_cache: dict[tuple[int, int], list[int]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.n = self.graph.number_of_nodes()
        if set(self.graph.nodes) != set(range(self.n)):
            raise ValueError("node labels must be exactly 0..n-1; reindex the graph first")

        self.rank = [NO_PARENT] * self.n
        self._needs_recompute = [False] * self.n
        self._contracted_edges = []
        self._unpack_cache = {}
        self.weight_backward = {}
        self.shortcut = {u: {} for u in range(self.n)}
        self.weight = self._collapse_parallel_edges()
        self._work = nx.DiGraph()
        self._work.add_nodes_from(range(self.n))
        self._work.add_edges_from((u, v) for u, vs in self.weight.items() for v in vs)

    # ---------------------------------------------------------------- setup

    def _collapse_parallel_edges(self) -> dict[int, dict[int, float]]:
        """Keep the cheapest edge of every parallel bundle; seed the shortcut table."""
        weight: dict[int, dict[int, float]] = {u: {} for u in range(self.n)}
        for u, v, length in self.graph.edges(data="length"):
            if length is None:
                continue
            row = weight[u]
            if v not in row or length < row[v]:
                row[v] = length

        for u, row in weight.items():
            for v, w in row.items():
                self._contracted_edges.append((u, v, w, NO_SHORTCUT))
                self.shortcut[u][v] = NO_SHORTCUT
        return weight

    # ------------------------------------------------------------ contraction

    def _local_search(
        self,
        source: int,
        avoid: int,
        limit: float,
        max_hops: int,
    ) -> dict[int, float]:
        """Bounded witness search: does a path around ``avoid`` beat ``limit``?

        Capped by hop count, distance and number of settled nodes (``theta``) so
        that contracting a node stays cheap on a graph of this size.
        """
        pq: list[tuple[float, int, int]] = [(0.0, source, 0)]
        dist = {source: 0.0}
        settled: set[int] = set()

        while pq and len(settled) <= self.theta:
            d, u, hops = heappop(pq)
            if u == avoid or u in settled:
                continue
            if hops >= max_hops or d > limit:
                continue
            settled.add(u)

            for v, w in self.weight[u].items():
                if v == avoid:
                    continue
                nd = d + w
                if nd <= limit and (v not in dist or nd < dist[v]):
                    dist[v] = nd
                    heappush(pq, (nd, v, hops + 1))
        return dist

    def _required_shortcuts(self, node: int) -> Iterator[tuple[int, int, float]]:
        """Shortcuts that must replace ``node`` to preserve all shortest paths."""
        successors = list(self._work.successors(node))
        predecessors = list(self._work.predecessors(node))
        if not successors or not predecessors:
            return

        for u in predecessors:
            if u == node:
                continue
            w_in = self.weight[u][node]
            via = {v: w_in + self.weight[node][v] for v in successors if v != node and v != u}
            if not via:
                continue

            witness = self._local_search(
                source=u, avoid=node, limit=max(via.values()), max_hops=self.max_hops
            )
            for v, through in via.items():
                if v not in witness or witness[v] > through:
                    yield u, v, through

    def _edge_difference(self, node: int) -> int:
        """Contraction priority: shortcuts added minus original edges removed."""
        added = sum(1 for _ in self._required_shortcuts(node))
        return added - self._work.in_degree(node) - self._work.out_degree(node)

    def preprocess(self, progress: bool = False) -> None:
        """Contract every node in lazy edge-difference order, recording shortcuts."""
        pq = []
        for node in range(self.n):
            heappush(pq, (self._edge_difference(node), node))
            self._needs_recompute[node] = False

        bar = None
        if progress:
            from tqdm import tqdm

            bar = tqdm(total=self.n, desc="contracting")

        order = 0
        while pq:
            _, node = heappop(pq)

            # Lazy update: a stale priority only matters if it is no longer the minimum.
            if self._needs_recompute[node]:
                score = self._edge_difference(node)
                self._needs_recompute[node] = False
                if pq and score > pq[0][0]:
                    heappush(pq, (score, node))
                    continue

            self.rank[node] = order
            order += 1
            if bar is not None:
                bar.update(1)

            for u, v, w in list(self._required_shortcuts(node)):
                if not self._work.has_edge(u, v):
                    self._work.add_edge(u, v)
                self.weight[u][v] = w
                self.shortcut[u][v] = node

            for u in list(self._work.predecessors(node)):
                if u == node:
                    continue
                self._needs_recompute[u] = True
                self._contracted_edges.append(
                    (u, node, self.weight[u][node], self.shortcut[u][node])
                )
                del self.weight[u][node], self.shortcut[u][node]

            for v in list(self._work.successors(node)):
                if v == node:
                    continue
                self._needs_recompute[v] = True
                self._contracted_edges.append(
                    (node, v, self.weight[node][v], self.shortcut[node][v])
                )
                del self.weight[node][v], self.shortcut[node][v]

            self._work.remove_node(node)

        if bar is not None:
            bar.close()
        self._build_search_graphs()

    def _build_search_graphs(self) -> None:
        """Rebuild the upward/downward adjacency used at query time."""
        self.weight = {u: {} for u in range(self.n)}
        self.shortcut = {u: {} for u in range(self.n)}
        self.weight_backward = {u: {} for u in range(self.n)}

        for u, v, w, via in self._contracted_edges:
            if v not in self.weight[u] or w < self.weight[u][v]:
                self.weight[u][v] = w
                self.shortcut[u][v] = via
                self.weight_backward[v][u] = w
        self._contracted_edges = []
        self._work = nx.DiGraph()

    # ------------------------------------------------------------- unpacking

    def unpack(self, u: int, v: int) -> list[int]:
        """Nodes hidden inside shortcut ``(u, v)``, in path order (empty for a real edge)."""
        if self.shortcut[u][v] == NO_SHORTCUT:
            return []

        cached = self._unpack_cache.get((u, v))
        if cached is not None:
            return cached

        out: list[int] = []
        stack: list[tuple[int, int, bool]] = [(u, v, False)]
        while stack:
            a, b, is_node = stack.pop()
            if is_node:
                out.append(a)
                continue
            via = self.shortcut[a][b]
            if via == NO_SHORTCUT:
                continue
            stack.append((via, b, False))
            stack.append((via, via, True))
            stack.append((a, via, False))

        if len(self._unpack_cache) >= self.unpack_cache_size:
            self._unpack_cache.clear()
        self._unpack_cache[(u, v)] = out
        return out

    def _expand(self, parent: dict[int, int], node: int, forward: bool) -> list[int]:
        """Walk the parent chain from ``node`` back to its root, expanding shortcuts.

        Returns nodes ordered from ``node`` towards the root.
        """
        path = []
        while True:
            path.append(node)
            up = parent.get(node, NO_PARENT)
            if up == NO_PARENT:
                return path
            hidden = self.unpack(up, node) if forward else self.unpack(node, up)
            path.extend(reversed(hidden) if forward else hidden)
            node = up

    # ----------------------------------------------------------------- query

    def search(self, source: int, backward: bool = False) -> SearchResult:
        """Upward Dijkstra from ``source``, counting shortest paths (Brandes' first phase)."""
        weight = self.weight_backward if backward else self.weight
        rank = self.rank

        pq: list[tuple[float, int]] = [(0.0, source)]
        dist = {source: 0.0}
        parent: dict[int, int] = {source: NO_PARENT}
        counts = {source: 1}
        predecessors: dict[int, list[int]] = {}
        settled: list[int] = []
        seen: set[int] = set()

        while pq:
            d, u = heappop(pq)
            if u in seen:
                continue
            seen.add(u)
            settled.append(u)
            count_u = counts[u]

            for v, w in weight[u].items():
                if rank[u] >= rank[v] or v in seen:
                    continue
                nd = d + w
                known = dist.get(v)
                if known is not None and nd == known:
                    counts[v] += count_u
                    predecessors[v].append(u)
                elif known is None or nd < known:
                    dist[v] = nd
                    parent[v] = u
                    counts[v] = count_u
                    predecessors[v] = [u]
                    heappush(pq, (nd, v))

        return SearchResult(source, dist, parent, counts, settled, predecessors)

    def distance(self, source: int, target: int) -> float:
        """Shortest-path cost, or ``inf`` if unreachable."""
        forward = self.search(source)
        backward = self.search(target, backward=True)
        return self._meet(forward.dist, backward.dist)[1]

    @staticmethod
    def _meet(dist_s: dict[int, float], dist_t: dict[int, float]) -> tuple[int | None, float]:
        best_node, best = None, math.inf
        for node, d in dist_s.items():
            other = dist_t.get(node)
            if other is not None and d + other < best:
                best_node, best = node, d + other
        return best_node, best

    def query(self, source: int, target: int) -> QueryResult:
        """Full bidirectional query returning the unpacked node path."""
        start = time.perf_counter()
        forward = self.search(source)
        backward = self.search(target, backward=True)
        meet, length = self._meet(forward.dist, backward.dist)
        latency = time.perf_counter() - start

        if meet is None:
            return QueryResult(source, target, math.inf, [], latency)

        head = self._expand(forward.parent, meet, forward=True)
        head.reverse()
        tail = self._expand(backward.parent, meet, forward=False)
        return QueryResult(source, target, length, head + tail[1:], latency)
