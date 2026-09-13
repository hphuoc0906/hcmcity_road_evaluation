"""Command line entry point: ``roadnet <command>``."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="roadnet", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("extract-region", help="clip a country .osm.pbf down to one city")
    p.add_argument("--region", default="Ho Chi Minh City, Vietnam")
    p.add_argument("--source", type=Path, required=True, help="country-level .osm.pbf")
    p.add_argument("--output", type=Path, default=Path("data/hochiminh.osm.pbf"))
    p.set_defaults(func=_extract_region)

    p = sub.add_parser("build-graph", help="turn an .osm.pbf into a preprocessed graph pickle")
    p.add_argument("--pbf", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("data/graph.pkl"))
    p.set_defaults(func=_build_graph)

    p = sub.add_parser("benchmark", help="time dijkstra / astar / ch over sampled queries")
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--algorithm", choices=["dijkstra", "astar", "ch"], required=True)
    p.add_argument("--queries", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=Path)
    p.set_defaults(func=_benchmark)

    p = sub.add_parser("betweenness", help="approximate edge betweenness over sampled sources")
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--samples", type=int, default=20_000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=Path, default=Path("data/betweenness.csv"))
    p.set_defaults(func=_betweenness)

    p = sub.add_parser("simulate-removal", help="remove top streets and measure the cost increase")
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--betweenness", type=Path, required=True)
    p.add_argument("--topk", type=int, default=100)
    p.add_argument("--mode", choices=["cumulative", "independent"], default="cumulative")
    p.add_argument("--benchmark-size", type=int, default=1000)
    p.add_argument("--output", type=Path, default=Path("data/removals.json"))
    p.set_defaults(func=_simulate_removal)

    p = sub.add_parser("build-cache", help="flatten the graph pickle into numpy arrays")
    p.add_argument("--graph", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path(".cache"))
    p.set_defaults(func=_build_cache)

    p = sub.add_parser("export-web", help="write the binary payloads for the web viewer")
    p.add_argument("--cache", type=Path, default=Path(".cache"))
    p.add_argument("--betweenness", type=Path, required=True)
    p.add_argument("--removals", type=Path)
    p.add_argument("--out", type=Path, default=Path("web/public/data"))
    p.add_argument("--top-k", type=int, default=60_000)
    p.add_argument("--bench-dijkstra", type=Path)
    p.add_argument("--bench-astar", type=Path)
    p.add_argument("--bench-ch", type=Path)
    p.set_defaults(func=_export_web)

    args = parser.parse_args(argv)
    return args.func(args) or 0


def _extract_region(args) -> None:
    from .data.extract import extract_region

    print(extract_region(args.region, args.source, args.output))


def _build_graph(args) -> None:
    from .data.preprocess import build_graph_from_pbf, save_graph

    graph = build_graph_from_pbf(args.pbf)
    save_graph(graph, args.output)
    print(f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges -> {args.output}")


def _benchmark(args) -> None:
    from .benchmark import latency_by_band, run_benchmark
    from .ch import ContractionHierarchies
    from .data.preprocess import load_graph
    from .sampling import sample_node_pairs

    graph = load_graph(args.graph)
    pairs = sample_node_pairs(graph, k=args.queries, seed=args.seed)

    ch = None
    if args.algorithm == "ch":
        ch = ContractionHierarchies(graph)
        ch.preprocess(progress=True)

    records = run_benchmark(graph, pairs, args.algorithm, ch=ch, output=args.output)
    print(json.dumps(latency_by_band(records), indent=2))


def _betweenness(args) -> None:
    from .betweenness import edge_betweenness_centrality
    from .ch import ContractionHierarchies
    from .data.preprocess import load_graph

    graph = load_graph(args.graph)
    ch = ContractionHierarchies(graph)
    ch.preprocess(progress=True)

    scores = edge_betweenness_centrality(graph, ch, k=args.samples, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["u", "v", "key", "betweenness"])
        for (u, v, key), value in scores.items():
            writer.writerow([u, v, key, value])
    print(f"{len(scores)} edges -> {args.output}")


def _simulate_removal(args) -> None:
    import pandas as pd

    from .data.preprocess import load_graph
    from .removal import simulate_removals

    graph = load_graph(args.graph)
    steps = simulate_removals(
        graph,
        pd.read_csv(args.betweenness),
        topk=args.topk,
        mode=args.mode,
        benchmark_size=args.benchmark_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([s.as_dict() for s in steps], indent=2))
    print(f"{len(steps)} removal steps -> {args.output}")


def _build_cache(args) -> None:
    from .export.cache import build_cache

    print(build_cache(args.graph, args.out))


def _export_web(args) -> None:
    from .export.webdata import export_web_data

    benchmarks = {
        name: path
        for name, path in (
            ("dijkstra", args.bench_dijkstra),
            ("astar", args.bench_astar),
            ("ch", args.bench_ch),
        )
        if path
    }
    meta = export_web_data(
        cache_dir=args.cache,
        betweenness_csv=args.betweenness,
        out_dir=args.out,
        removals=args.removals,
        benchmarks=benchmarks,
        top_k=args.top_k,
    )
    print(json.dumps({k: v for k, v in meta.items() if k != "topRoads"}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
