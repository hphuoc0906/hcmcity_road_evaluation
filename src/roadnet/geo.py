"""Geographic helpers."""

from __future__ import annotations

import math

import networkx as nx

EARTH_RADIUS_M = 6_371_000.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def node_distance(graph: nx.Graph, u: int, v: int) -> float:
    """Straight-line distance between two graph nodes, an admissible A* heuristic."""
    a, b = graph.nodes[u], graph.nodes[v]
    return haversine(a["y"], a["x"], b["y"], b["x"])
