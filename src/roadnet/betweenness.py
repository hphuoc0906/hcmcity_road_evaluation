"""Approximate edge betweenness centrality on a Contraction Hierarchy.

Brandes' dependency accumulation, but run over the CH upward search so each
sampled source costs a fraction of a full Dijkstra. Shortcuts are unpacked
before credit is assigned, so the score lands on real road segments.

What the approximation does and does not give you
-------------------------------------------------
The sweep from a source only follows edges that climb the hierarchy, so it sees
the *first half* of each shortest path — the part from the source up to the
meeting node. The second half is credited when the other endpoint is sampled.

The consequence is that these are **relative scores for ranking**, not absolute
centrality values:

* totals come out well below exact betweenness (``tests/test_ch.py`` pins this);
* the two directions of a street can differ sharply, since a given source
  credits only the direction it climbs;
* bottlenecks that every route must cross still rank at the top, which is what
  the criticality analysis needs.

Use :func:`networkx.edge_betweenness_centrality` if you need exact values on a
graph small enough to afford them.
"""

from __future__ import annotations

from collections.abc import Sequence

import networkx as nx

from .ch import ContractionHierarchies, SearchResult
from .sampling import sample_sources


def accumulate(
    betweenness: dict[tuple[int, int], float],
    result: SearchResult,
    ch: ContractionHierarchies,
) -> None:
    """Add one source's dependency contribution to ``betweenness`` in place."""
    delta = dict.fromkeys(result.settled, 0.0)
    counts = result.path_counts
    order = list(result.settled)

    while order:
        u = order.pop()
        if u == result.source:
            break
        coeff = (1 + delta[u]) / counts[u]
        for v in result.predecessors.get(u, ()):
            credit = counts[v] * coeff
            chain = [v, *ch.unpack(v, u), u]
            for i in range(len(chain) - 1, 0, -1):
                head = chain[i - 1]
                if head in delta:
                    delta[head] += credit
                betweenness[(head, chain[i])] += credit


def rescale(
    betweenness: dict, n: int, k: int | None = None, normalized: bool = True, directed: bool = False
) -> dict:
    """Scale raw dependency sums to comparable centrality values."""
    if normalized:
        if n <= 1:
            return betweenness
        scale = 1.0 / (n * (n - 1))
    else:
        scale = 1.0 if directed else 0.5

    if k is not None and k < n:
        scale *= n / k

    for edge in betweenness:
        betweenness[edge] *= scale
    return betweenness


def split_across_parallel_edges(
    graph: nx.MultiDiGraph, betweenness: dict[tuple[int, int], float], weight: dict
) -> dict[tuple[int, int, int], float]:
    """Spread each (u, v) score over the parallel edges that carry its cost.

    The hierarchy collapses parallel edges to the cheapest one, so the score is
    shared by every original edge whose length matches that cost.
    """
    if not graph.is_multigraph():
        return betweenness  # type: ignore[return-value]

    per_key: dict[tuple[int, int, int], float] = {}
    for (u, v), score in betweenness.items():
        target = weight[u].get(v)
        if target is None:
            continue
        keys = [
            key for key, data in graph[u][v].items() if abs(data.get("length", 1) - target) < 1e-4
        ]
        if not keys:
            continue
        share = score / len(keys)
        for key in keys:
            per_key[(u, v, key)] = share
    return per_key


def edge_betweenness_centrality(
    graph: nx.MultiDiGraph,
    ch: ContractionHierarchies,
    sources: Sequence[int] | None = None,
    k: int = 10_000,
    seed: int = 42,
    progress: bool = True,
) -> dict:
    """Approximate edge betweenness from ``k`` sampled sources."""
    if sources is None:
        sources = sample_sources(graph, k=k, seed=seed)

    betweenness = dict.fromkeys(graph.edges(), 0.0)

    iterator: Sequence[int] = sources
    if progress:
        from tqdm import tqdm

        iterator = tqdm(sources, desc="betweenness")

    for source in iterator:
        accumulate(betweenness, ch.search(source), ch)

    betweenness = rescale(
        betweenness,
        n=graph.number_of_nodes(),
        k=len(sources),
        normalized=True,
        directed=graph.is_directed(),
    )
    return split_across_parallel_edges(graph, betweenness, ch.weight)
