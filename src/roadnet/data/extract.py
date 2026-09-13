"""Cut a city-sized OSM extract out of a country-sized one with osmconvert."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def write_poly_file(polygon, path: Path, name: str = "region") -> Path:
    """Write a shapely (Multi)Polygon in the osmosis ``.poly`` boundary format."""
    with path.open("w") as f:
        f.write(f"{name}\n")
        rings = [polygon] if polygon.geom_type == "Polygon" else list(polygon.geoms)
        if polygon.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"expected a Polygon or MultiPolygon, got {polygon.geom_type}")
        for i, ring in enumerate(rings, 1):
            f.write(f"{i}\n")
            for x, y in ring.exterior.coords:
                f.write(f"  {x} {y}\n")
            f.write("END\n")
        f.write("END\n")
    return path


def extract_region(
    region: str,
    source_pbf: Path,
    output_pbf: Path,
    poly_path: Path | None = None,
) -> Path:
    """Geocode ``region``, then clip ``source_pbf`` to its boundary.

    Requires the ``osm`` extra for geocoding and the ``osmconvert`` binary on PATH
    (Debian/Ubuntu: ``apt install osmctools``).
    """
    import osmnx as ox

    if shutil.which("osmconvert") is None:
        raise RuntimeError("osmconvert not found on PATH; install the osmctools package")

    poly_path = poly_path or output_pbf.with_suffix(".poly")
    boundary = ox.geocode_to_gdf(region).geometry.values[0]
    write_poly_file(boundary, poly_path, name=region)

    output_pbf.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["osmconvert", str(source_pbf), f"-B={poly_path}", f"-o={output_pbf}"], check=True
    )
    return output_pbf
