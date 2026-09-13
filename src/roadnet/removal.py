"""Edge-removal simulation: how much does the network cost when a road is lost?

A single high-betweenness edge is rarely meaningful on its own — adjacent edges
along the same street carry nearly identical scores. So a whole run of
equal-scoring edges is removed together, the hierarchy is rebuilt, and the
benchmark travel cost is re-measured.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

import networkx as nx
import pandas as pd

from .ch import ContractionHierarchies
from .sampling import sample_node_pairs

Mode = Literal["cumulative", "independent"]
SCORE_TOLERANCE = 1e-6


@dataclass(slots=True)
class RemovalStep:
    rank: int
    seed_edge: tuple[int, int, int]
    seed_betweenness: float
    removed_edges: list[tuple[int, int, int]]
    baseline_cost: float
    cost: float
    delta_cost: float
    cumulative_delta: float
    road_name: str | None = None

    def as_dict(self) -> dict:
        return {
            "rank": self.rank,
            "seed_edge": list(self.seed_edge),
            "seed_betweenness": self.seed_betweenness,
            "removed_edges": [list(e) for e in self.removed_edges],
            "baseline_cost": self.baseline_cost,
            "cost": self.cost,
            "delta_cost": self.delta_cost,
            "cumulative_delta": self.cumulative_delta,
            "road_name": self.road_name,
        }


@dataclass(slots=True)
class _Segments:
    """Index of scored edges, used to grow a street run out of one seed edge."""

    edges: list[tuple[int, int, int, float]]
    incident: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    consumed: list[bool] = field(default_factory=list)

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> _Segments:
        ordered = frame.sort_values("betweenness", ascending=False)
        edges = [
            (int(r.u), int(r.v), int(r.key), float(r.betweenness))
            for r in ordered.itertuples(index=False)
        ]
        index = cls(edges=edges, consumed=[False] * len(edges))
        for i, (u, v, _, _) in enumerate(edges):
            index.incident[u].append(i)
            index.incident[v].append(i)
        return index

    def grow_run(self, start: int) -> list[int]:
        """Collect edges reachable from ``start`` whose score matches within tolerance."""
        u, v, _, score = self.edges[start]
        run: list[int] = []
        seen: set[int] = set()
        stack = [(u, score), (v, score)]

        while stack:
            node, expected = stack.pop()
            for idx in self.incident[node]:
                if idx in seen or self.consumed[idx]:
                    continue
                seen.add(idx)
                eu, ev, _, escore = self.edges[idx]
                if abs(expected - escore) >= SCORE_TOLERANCE:
                    continue
                self.consumed[idx] = True
                run.append(idx)
                stack.append((eu + ev - node, escore))
        return run


def _benchmark_cost(graph: nx.MultiDiGraph, pairs: list[tuple[int, int]]) -> float:
    """Total shortest-path cost over the benchmark pairs, via a freshly built CH."""
    ch = ContractionHierarchies(graph)
    ch.preprocess()
    return sum(ch.distance(u, v) for u, v in pairs)


def simulate_removals(
    graph: nx.MultiDiGraph,
    betweenness: pd.DataFrame,
    topk: int = 10,
    mode: Mode = "cumulative",
    pairs: list[tuple[int, int]] | None = None,
    benchmark_size: int = 1000,
    seed: int = 42,
    progress: bool = True,
) -> list[RemovalStep]:
    """Remove the ``topk`` highest-betweenness street runs and measure the damage.

    ``cumulative`` keeps every removal in place, so costs compound; ``independent``
    restores each run before the next, isolating the effect of losing one street.
    """
    working = copy.deepcopy(graph)
    segments = _Segments.from_frame(betweenness)
    if pairs is None:
        pairs = sample_node_pairs(working, k=benchmark_size, seed=seed)

    initial_cost = _benchmark_cost(working, pairs)
    baseline = initial_cost
    steps: list[RemovalStep] = []

    bar = None
    if progress:
        from tqdm import tqdm

        bar = tqdm(total=topk, desc=f"removals ({mode})")

    cursor = 0
    while len(steps) < topk and cursor < len(segments.edges):
        while cursor < len(segments.edges) and segments.consumed[cursor]:
            cursor += 1
        if cursor >= len(segments.edges):
            break

        seed_idx = cursor
        u, v, key, score = segments.edges[seed_idx]
        run = segments.grow_run(seed_idx)
        cursor += 1

        detached: list[tuple[int, int, int, dict]] = []
        for idx in run:
            ru, rv, rkey, _ = segments.edges[idx]
            if working.has_edge(ru, rv, rkey):
                detached.append((ru, rv, rkey, working[ru][rv][rkey].copy()))
                working.remove_edge(ru, rv, rkey)
        if not detached:
            continue

        cost = _benchmark_cost(working, pairs)
        steps.append(
            RemovalStep(
                rank=len(steps) + 1,
                seed_edge=(u, v, key),
                seed_betweenness=score,
                removed_edges=[(a, b, c) for a, b, c, _ in detached],
                baseline_cost=baseline,
                cost=cost,
                delta_cost=cost - baseline,
                cumulative_delta=cost - initial_cost,
            )
        )
        if bar is not None:
            bar.update(1)

        if mode == "cumulative":
            baseline = cost
        else:
            for ru, rv, rkey, data in detached:
                working.add_edge(ru, rv, key=rkey, **data)

    if bar is not None:
        bar.close()
    return steps
