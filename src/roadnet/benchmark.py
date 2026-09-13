"""Latency benchmarks for Dijkstra, A* and Contraction Hierarchies."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import networkx as nx

from .ch import ContractionHierarchies
from .geo import node_distance
from .sampling import DEGREE_BANDS

Algorithm = Literal["dijkstra", "astar", "ch"]


@dataclass(slots=True)
class QueryRecord:
    algorithm: str
    source: int
    target: int
    latency_s: float
    path_length: float
    path_nodes: list[int]


def run_query(
    graph: nx.MultiDiGraph,
    source: int,
    target: int,
    algorithm: Algorithm,
    ch: ContractionHierarchies | None = None,
) -> QueryRecord:
    """Time a single point-to-point query."""
    if algorithm == "ch":
        if ch is None:
            raise ValueError("the 'ch' algorithm needs a preprocessed hierarchy")
        result = ch.query(source, target)
        return QueryRecord("ch", source, target, result.latency_s, result.length, result.nodes)

    start = time.perf_counter()
    if algorithm == "dijkstra":
        path = nx.dijkstra_path(graph, source, target, weight="length")
    elif algorithm == "astar":
        path = nx.astar_path(
            graph,
            source,
            target,
            heuristic=lambda u, v: node_distance(graph, u, v),
            weight="length",
        )
    else:
        raise ValueError(f"unknown algorithm: {algorithm}")
    latency = time.perf_counter() - start

    return QueryRecord(
        algorithm, source, target, latency, nx.path_weight(graph, path, weight="length"), path
    )


def run_benchmark(
    graph: nx.MultiDiGraph,
    pairs: list[tuple[int, int]],
    algorithm: Algorithm,
    ch: ContractionHierarchies | None = None,
    output: Path | None = None,
    progress: bool = True,
) -> list[QueryRecord]:
    """Run every pair and optionally write the records as JSON."""
    iterator = pairs
    if progress:
        from tqdm import tqdm

        iterator = tqdm(pairs, desc=algorithm)

    records = [run_query(graph, u, v, algorithm, ch) for u, v in iterator]

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps([asdict(r) for r in records], indent=2))
    return records


def latency_by_band(records: list[QueryRecord], bands: int = len(DEGREE_BANDS)) -> dict[str, float]:
    """Mean latency per degree band, assuming pairs were generated band by band."""
    total = len(records)
    size = total // bands
    summary = {}
    for i in range(bands):
        chunk = records[i * size : total if i == bands - 1 else (i + 1) * size]
        if chunk:
            summary[f"deg_level_{i + 1}"] = sum(r.latency_s for r in chunk) / len(chunk)
    summary["overall"] = sum(r.latency_s for r in records) / len(records)
    return summary


def validate_path(graph: nx.MultiDiGraph, path: list[int]) -> bool:
    """Every consecutive pair must be a real edge — catches broken shortcut unpacking."""
    return all(graph.has_edge(path[i], path[i + 1]) for i in range(len(path) - 1))
