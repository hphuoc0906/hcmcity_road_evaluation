import math
import random

import networkx as nx
import pytest

from roadnet.benchmark import validate_path
from roadnet.betweenness import edge_betweenness_centrality
from roadnet.ch import ContractionHierarchies


def grid_graph(rows: int = 6, cols: int = 6, seed: int = 7) -> nx.MultiDiGraph:
    """Jittered grid: dense enough to force shortcuts, small enough to brute force."""
    rng = random.Random(seed)
    G = nx.MultiDiGraph()
    node = lambda r, c: r * cols + c  # noqa: E731

    for r in range(rows):
        for c in range(cols):
            G.add_node(node(r, c), x=c * 0.001 + 106.6, y=r * 0.001 + 10.7)

    for r in range(rows):
        for c in range(cols):
            for dr, dc in ((0, 1), (1, 0)):
                nr, nc = r + dr, c + dc
                if nr >= rows or nc >= cols:
                    continue
                length = 100 + rng.random() * 50
                G.add_edge(node(r, c), node(nr, nc), length=length)
                G.add_edge(node(nr, nc), node(r, c), length=length)
    return G


@pytest.fixture(scope="module")
def hierarchy():
    G = grid_graph()
    ch = ContractionHierarchies(G)
    ch.preprocess()
    return G, ch


def test_every_node_gets_a_rank(hierarchy):
    G, ch = hierarchy
    assert sorted(ch.rank) == list(range(G.number_of_nodes()))


def test_distances_match_dijkstra(hierarchy):
    G, ch = hierarchy
    for source in G.nodes:
        reference = nx.single_source_dijkstra_path_length(G, source, weight="length")
        for target in G.nodes:
            expected = reference.get(target, math.inf)
            assert ch.distance(source, target) == pytest.approx(expected, rel=1e-9)


def test_query_returns_a_real_path_of_the_right_length(hierarchy):
    G, ch = hierarchy
    for source, target in ((0, 35), (35, 0), (3, 30), (17, 17)):
        result = ch.query(source, target)
        assert validate_path(G, result.nodes)
        assert result.nodes[0] == source
        assert result.nodes[-1] == target
        assert nx.path_weight(G, result.nodes, weight="length") == pytest.approx(result.length)


def test_query_keeps_the_target_when_it_is_the_meeting_node(hierarchy):
    """Regression: the meeting node used to be dropped when it was the target itself."""
    G, ch = hierarchy
    for source in G.nodes:
        for target in G.nodes:
            if source == target:
                continue
            nodes = ch.query(source, target).nodes
            assert nodes[-1] == target, f"{source}->{target} lost its endpoint"


def test_unpacked_shortcuts_only_contain_real_edges(hierarchy):
    G, ch = hierarchy
    for u, row in ch.shortcut.items():
        for v, via in row.items():
            chain = [u, *ch.unpack(u, v), v]
            assert validate_path(G, chain)
            if via != -1:
                assert len(chain) > 2


def bridged_clusters() -> tuple[nx.MultiDiGraph, tuple[int, int]]:
    """Two grids joined by a single edge — the textbook bottleneck."""
    G = nx.MultiDiGraph()
    ids = {(s, r, c): (s * 16) + r * 4 + c for s in (0, 1) for r in range(4) for c in range(4)}
    for node in ids.values():
        G.add_node(node, x=0.0, y=0.0)

    def link(a, b):
        G.add_edge(a, b, length=100.0)
        G.add_edge(b, a, length=100.0)

    for s in (0, 1):
        for r in range(4):
            for c in range(4):
                if c < 3:
                    link(ids[(s, r, c)], ids[(s, r, c + 1)])
                if r < 3:
                    link(ids[(s, r, c)], ids[(s, r + 1, c)])

    bridge = (ids[(0, 1, 3)], ids[(1, 1, 0)])
    link(*bridge)
    return G, bridge


def test_betweenness_finds_the_bottleneck():
    """The approximation's whole purpose: surface the edge every route must cross."""
    G, bridge = bridged_clusters()
    ch = ContractionHierarchies(G)
    ch.preprocess()

    scores = edge_betweenness_centrality(
        G, ch, sources=list(G.nodes), k=G.number_of_nodes(), progress=False
    )
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    assert ranked[0][0][:2] == bridge

    exact = nx.edge_betweenness_centrality(G, normalized=True, weight="length")
    assert max(exact, key=exact.get)[:2] == bridge


def test_betweenness_is_accumulated_from_one_side_only():
    """Documents a known limit: the upward-only sweep credits one direction of a pair.

    Scores are comparable for ranking, not as absolute centrality values — see
    the caveat in ``roadnet.betweenness``.
    """
    G, bridge = bridged_clusters()
    ch = ContractionHierarchies(G)
    ch.preprocess()

    scores = edge_betweenness_centrality(
        G, ch, sources=list(G.nodes), k=G.number_of_nodes(), progress=False
    )
    forward = max(v for (a, b, _), v in scores.items() if (a, b) == bridge)
    reverse = max(v for (a, b, _), v in scores.items() if (a, b) == bridge[::-1])
    assert forward > 0
    assert reverse < forward

    exact = nx.edge_betweenness_centrality(G, normalized=True, weight="length")
    assert sum(scores.values()) < sum(exact.values())


def test_rejects_non_contiguous_node_labels():
    G = nx.MultiDiGraph()
    G.add_edge(5, 9, length=1.0)
    with pytest.raises(ValueError, match="0..n-1"):
        ContractionHierarchies(G)
