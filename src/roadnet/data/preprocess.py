"""Turn an OSM extract into the directed, reindexed graph the hierarchy expects."""

from __future__ import annotations

import pickle
from pathlib import Path

import networkx as nx

TWO_WAY_TAGS = {"no", "none", "nan", ""}


def preprocess_graph(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Normalise an OSM graph: drop unusable edges, apply oneway tags, reindex nodes.

    Steps, in order:
      1. relabel nodes to ``0..n-1`` so the hierarchy can index them as arrays;
      2. drop edges with no length and self loops, which carry no routing information;
      3. materialise both directions of every two-way street (``oneway=-1`` flips it).
    """
    graph = nx.relabel_nodes(graph, {nid: i for i, nid in enumerate(graph.nodes)}, copy=True)

    graph.remove_edges_from(
        [
            (u, v, k)
            for u, v, k, data in graph.edges(keys=True, data=True)
            if data.get("length") is None or u == v
        ]
    )

    to_add: list[tuple[int, int, dict]] = []
    to_remove: list[tuple[int, int, int]] = []
    for u, v, k, data in graph.edges(keys=True, data=True):
        oneway = str(data.get("oneway", "")).lower()
        if oneway == "yes":
            continue
        if oneway == "-1":
            to_add.append((v, u, data.copy()))
            to_remove.append((u, v, k))
        else:
            # Unknown tags are treated as two-way, which is OSM's own default.
            to_add.append((v, u, data.copy()))

    graph.remove_edges_from(to_remove)
    for u, v, data in to_add:
        graph.add_edge(u, v, **data)

    return graph


def build_graph_from_pbf(pbf: Path, network_type: str = "all") -> nx.MultiDiGraph:
    """Read an ``.osm.pbf`` extract into a preprocessed graph (needs the ``osm`` extra)."""
    from pyrosm import OSM

    osm = OSM(str(pbf))
    nodes, edges = osm.get_network(network_type=network_type, nodes=True)
    return preprocess_graph(osm.to_graph(nodes, edges, graph_type="networkx"))


def save_graph(graph: nx.MultiDiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(graph, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_graph(path: Path) -> nx.MultiDiGraph:
    with path.open("rb") as f:
        return pickle.load(f)
