"""Pack the analysis results into the binary payloads the web viewer loads.

Two tiers, because 1.2 M segments is too much to download up front:

``top.bin``      the highest-betweenness edges at full float precision (~1 MB)
``network.bin``  every edge, coordinates quantised to 16 bits (~11 MB, opt-in)

16-bit quantisation over the city bounding box resolves to about one metre,
which is below what a line 1-2 px wide can show anyway.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .cache import load_cache

QUANT_MAX = 65535


@dataclass(slots=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def as_dict(self) -> dict:
        return {"minX": self.min_x, "minY": self.min_y, "maxX": self.max_x, "maxY": self.max_y}


def _quantize(values: np.ndarray, low: float, high: float) -> np.ndarray:
    span = high - low or 1.0
    return np.clip(np.rint((values - low) / span * QUANT_MAX), 0, QUANT_MAX).astype(np.uint16)


def _intensity(betweenness: np.ndarray) -> np.ndarray:
    """Map scores to 0-255 by rank, so colour is spread evenly instead of clumped.

    Betweenness is heavily skewed — a few arterials dominate and almost everything
    else rounds to zero on a linear ramp.
    """
    order = np.argsort(betweenness)
    ranks = np.empty(len(betweenness), dtype=np.float64)
    ranks[order] = np.arange(len(betweenness))
    return np.rint(ranks / max(len(betweenness) - 1, 1) * 255).astype(np.uint8)


def export_web_data(
    cache_dir: Path,
    betweenness_csv: Path,
    out_dir: Path,
    removals: Path | None = None,
    benchmarks: dict[str, Path] | None = None,
    top_k: int = 60_000,
    top_roads: int = 40,
) -> dict:
    """Write ``meta.json``, ``top.bin``, ``network.bin``, ``removals.json`` into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cache, names = load_cache(cache_dir)

    node_x, node_y = cache["node_x"], cache["node_y"]
    edge_u, edge_v, edge_key = cache["edge_u"], cache["edge_v"], cache["edge_key"]

    scores = _betweenness_by_edge(betweenness_csv, edge_u, edge_v, edge_key)

    x1, y1 = node_x[edge_u], node_y[edge_u]
    x2, y2 = node_x[edge_v], node_y[edge_v]
    bounds = Bounds(
        float(min(x1.min(), x2.min())),
        float(min(y1.min(), y2.min())),
        float(max(x1.max(), x2.max())),
        float(max(y1.max(), y2.max())),
    )

    order = np.argsort(-scores, kind="stable")
    top = order[:top_k]

    top_coords = np.empty(len(top) * 4, dtype=np.float32)
    top_coords[0::4] = x1[top]
    top_coords[1::4] = y1[top]
    top_coords[2::4] = x2[top]
    top_coords[3::4] = y2[top]
    (out_dir / "top.bin").write_bytes(
        top_coords.tobytes() + scores[top].astype(np.float32).tobytes()
    )

    quant = np.empty(len(edge_u) * 4, dtype=np.uint16)
    quant[0::4] = _quantize(x1, bounds.min_x, bounds.max_x)
    quant[1::4] = _quantize(y1, bounds.min_y, bounds.max_y)
    quant[2::4] = _quantize(x2, bounds.min_x, bounds.max_x)
    quant[3::4] = _quantize(y2, bounds.min_y, bounds.max_y)
    (out_dir / "network.bin").write_bytes(quant.tobytes() + _intensity(scores).tobytes())

    removal_steps = []
    if removals is not None and removals.exists():
        removal_steps = _export_removals(removals, cache, names, out_dir)

    meta = {
        "generatedAt": pd.Timestamp.utcnow().isoformat(),
        "bounds": bounds.as_dict(),
        "nodeCount": int(len(node_x)),
        "edgeCount": int(len(edge_u)),
        "topCount": int(len(top)),
        "quantMax": QUANT_MAX,
        "betweenness": {
            "max": float(scores.max()),
            "min": float(scores.min()),
            "topThreshold": float(scores[top[-1]]) if len(top) else 0.0,
        },
        "topRoads": _rank_roads(scores, names, top_roads, x1, y1, x2, y2),
        "removalCount": len(removal_steps),
        "benchmarks": _summarise_benchmarks(benchmarks or {}),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


def _betweenness_by_edge(
    csv_path: Path, edge_u: np.ndarray, edge_v: np.ndarray, edge_key: np.ndarray
) -> np.ndarray:
    """Align the (u, v, key) scores in the CSV with the cache's edge ordering."""
    frame = pd.read_csv(csv_path)
    lookup = {
        (int(u), int(v), int(k)): float(b)
        for u, v, k, b in zip(frame.u, frame.v, frame.key, frame.betweenness, strict=True)
    }
    return np.array(
        [
            lookup.get((int(u), int(v), int(k)), 0.0)
            for u, v, k in zip(edge_u, edge_v, edge_key, strict=True)
        ],
        dtype=np.float64,
    )


def _rank_roads(
    scores: np.ndarray,
    names: list[str],
    limit: int,
    x1: np.ndarray,
    y1: np.ndarray,
    x2: np.ndarray,
    y2: np.ndarray,
) -> list[dict]:
    """Aggregate per-edge scores into a ranked street table, keyed by its peak segment."""
    peak: dict[str, tuple[float, int]] = {}
    totals: defaultdict[str, float] = defaultdict(float)
    for i, name in enumerate(names):
        if not name:
            continue
        score = float(scores[i])
        totals[name] += score
        if name not in peak or score > peak[name][0]:
            peak[name] = (score, i)

    ranked = sorted(peak.items(), key=lambda kv: -kv[1][0])[:limit]
    return [
        {
            "name": name,
            "betweenness": score,
            "totalBetweenness": totals[name],
            "segment": [float(x1[idx]), float(y1[idx]), float(x2[idx]), float(y2[idx])],
        }
        for name, (score, idx) in ranked
    ]


def _export_removals(path: Path, cache: dict, names: list[str], out_dir: Path) -> list[dict]:
    """Attach geometry and street names to each simulated removal."""
    raw = json.loads(path.read_text())
    node_x, node_y = cache["node_x"], cache["node_y"]
    edge_index = {
        (int(u), int(v), int(k)): i
        for i, (u, v, k) in enumerate(
            zip(cache["edge_u"], cache["edge_v"], cache["edge_key"], strict=True)
        )
    }

    # Legacy logs record absolute costs; derive the cumulative delta from the first baseline.
    initial_cost = (
        float(raw[0].get("baseline_cost", raw[0].get("last_shortest_path", 0.0))) if raw else 0.0
    )

    steps = []
    for rank, item in enumerate(raw, start=1):
        removed = [tuple(int(round(float(c))) for c in edge) for edge in item["delete_edges"]]
        segments = [
            [float(node_x[u]), float(node_y[u]), float(node_x[v]), float(node_y[v])]
            for u, v, _ in removed
            if u < len(node_x) and v < len(node_x)
        ]
        label = next(
            (names[edge_index[e]] for e in removed if e in edge_index and names[edge_index[e]]),
            "",
        )
        seed = item.get("seed_edge") or item.get("start_edge") or []
        steps.append(
            {
                "rank": rank,
                "roadName": label or "Unnamed road",
                "deltaCost": float(item.get("delta_cost", 0.0)),
                "cumulativeDelta": float(
                    item.get("cumulative_delta", item.get("shortest_length", 0.0) - initial_cost)
                ),
                "baselineCost": float(
                    item.get("baseline_cost", item.get("last_shortest_path", 0.0))
                ),
                "betweenness": float(seed[3]) if len(seed) > 3 else 0.0,
                "edgeCount": len(segments),
                "segments": segments,
            }
        )
    (out_dir / "removals.json").write_text(json.dumps(steps, ensure_ascii=False))
    return steps


def _summarise_benchmarks(paths: dict[str, Path]) -> dict:
    """Mean query latency per degree band, per algorithm."""
    from ..benchmark import QueryRecord, latency_by_band

    summary = {}
    for algorithm, path in paths.items():
        if not path or not Path(path).exists():
            continue
        records = [
            QueryRecord(
                algorithm,
                r["source"],
                r["target"],
                float(r["latency_s"]),
                float(r["path_length"]),
                [],
            )
            for r in json.loads(Path(path).read_text())
        ]
        if records:
            summary[algorithm] = latency_by_band(records)
    return summary
