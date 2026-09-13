"""Flatten the analysis graph into numpy arrays.

The pickled graph is ~440 MB and slow to load; every downstream consumer reads
these arrays instead. pyrosm splits ways at intersections, so each edge geometry
is a straight u -> v segment and node coordinates are enough to redraw it.
"""

from __future__ import annotations

import gzip
import pickle
from pathlib import Path

import numpy as np

CACHE_FILE = "graph_cache.npz"
NAMES_FILE = "edge_names.txt.gz"


def build_cache(graph_pickle: Path, out_dir: Path) -> Path:
    """Extract node coordinates and edge attributes into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with graph_pickle.open("rb") as f:
        graph = pickle.load(f)

    n = graph.number_of_nodes()
    node_x = np.empty(n, dtype=np.float64)
    node_y = np.empty(n, dtype=np.float64)
    for i, (_, data) in enumerate(graph.nodes(data=True)):
        node_x[i] = data["x"]
        node_y[i] = data["y"]

    m = graph.number_of_edges()
    edge_u = np.empty(m, dtype=np.int32)
    edge_v = np.empty(m, dtype=np.int32)
    edge_key = np.empty(m, dtype=np.int32)
    edge_length = np.empty(m, dtype=np.float64)
    edge_highway = np.zeros(m, dtype=np.int16)
    names: list[str] = []
    classes: dict[str, int] = {}

    for i, (u, v, k, data) in enumerate(graph.edges(keys=True, data=True)):
        edge_u[i] = u
        edge_v[i] = v
        edge_key[i] = k
        edge_length[i] = data.get("length") or 0.0
        names.append(_first_str(data.get("name")))
        highway = _first_str(data.get("highway"))
        edge_highway[i] = classes.setdefault(highway, len(classes))

    np.savez_compressed(
        out_dir / CACHE_FILE,
        node_x=node_x,
        node_y=node_y,
        edge_u=edge_u,
        edge_v=edge_v,
        edge_key=edge_key,
        edge_length=edge_length,
        edge_highway=edge_highway,
        highway_classes=np.array(sorted(classes, key=classes.__getitem__), dtype=object),
    )
    with gzip.open(out_dir / NAMES_FILE, "wt", encoding="utf-8") as f:
        f.write("\n".join(names))
    return out_dir / CACHE_FILE


def load_cache(cache_dir: Path) -> tuple[dict, list[str]]:
    """Read the arrays and the per-edge street names back."""
    data = dict(np.load(cache_dir / CACHE_FILE, allow_pickle=True))
    with gzip.open(cache_dir / NAMES_FILE, "rt", encoding="utf-8") as f:
        names = f.read().split("\n")
    return data, names


def _first_str(value) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    return str(value) if value else ""
