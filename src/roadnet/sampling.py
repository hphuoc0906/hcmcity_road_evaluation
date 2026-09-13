"""Degree-stratified query sampling.

Benchmarks split nodes into three degree bands so that easy (low-degree,
peripheral) and hard (high-degree, central) queries are equally represented
instead of being dominated by the long tail of degree-2 nodes.
"""

from __future__ import annotations

import random

import networkx as nx

DEGREE_BANDS: tuple[tuple[int, int], ...] = ((0, 4), (5, 9), (10, 1 << 30))


def degree_bands(graph: nx.Graph) -> list[list[int]]:
    """Partition nodes into the three degree bands used by the benchmarks."""
    degree = dict(graph.degree())
    bands: list[list[int]] = [[] for _ in DEGREE_BANDS]
    for node, deg in degree.items():
        for i, (low, high) in enumerate(DEGREE_BANDS):
            if low <= deg <= high:
                bands[i].append(node)
                break
    return bands


def sample_node_pairs(graph: nx.Graph, k: int = 1000, seed: int = 42) -> list[tuple[int, int]]:
    """``k`` (source, target) pairs, evenly split across degree bands."""
    rng = random.Random(seed)
    bands = degree_bands(graph)
    pairs: list[tuple[int, int]] = []

    for i, band in enumerate(bands):
        quota = k - len(pairs) if i == len(bands) - 1 else k // len(bands)
        if len(band) < 2:
            continue
        for _ in range(quota):
            u, v = rng.sample(band, 2)
            pairs.append((u, v))

    pool = [n for band in bands for n in band]
    while len(pairs) < k and len(pool) >= 2:
        pairs.append(tuple(rng.sample(pool, 2)))  # type: ignore[arg-type]
    return pairs


def sample_sources(
    graph: nx.Graph, k: int = 10_000, seed: int = 42, replace: bool = False
) -> list[int]:
    """``k`` distinct source nodes for Brandes sampling, evenly split across bands."""
    rng = random.Random(seed)
    bands = degree_bands(graph)
    sources: list[int] = []
    used: set[int] = set()

    for i, band in enumerate(bands):
        quota = k - len(sources) if i == len(bands) - 1 else k // len(bands)
        if replace:
            if band:
                sources.extend(rng.choice(band) for _ in range(quota))
            continue
        available = [n for n in band if n not in used]
        rng.shuffle(available)
        picked = available[:quota]
        sources.extend(picked)
        used.update(picked)

    if len(sources) < k:
        pool = [n for band in bands for n in band if replace or n not in used]
        rng.shuffle(pool)
        sources.extend(pool[: k - len(sources)])
    return sources
