import osmnx as ox
import subprocess
import argparse


def shapely_polygon_to_polyfile(polygon, filename="hochiminh.poly", name="TP_HCM"):
    def write_ring(f, coords):
        for x, y in coords:
            f.write(f"  {x} {y}\n")
        f.write("END\n")

    with open(filename, "w") as f:
        f.write(f"{name}\n")
        if polygon.geom_type == "Polygon":
            f.write("1\n")
            write_ring(f, polygon.exterior.coords)
            f.write("END\n")
        elif polygon.geom_type == "MultiPolygon":
            for i, poly in enumerate(polygon.geoms, 1):
                f.write(f"{i}\n")
                write_ring(f, poly.exterior.coords)
            f.write("END\n")
        else:
            raise ValueError("Not a valid Polygon or MultiPolygon")


def get_polygon_from_osm(region_name="Ho Chi Minh City, Vietnam",
                          osm_input_path="/kaggle/input/vietnammap/vietnam-latest.osm.pbf",
                          output_osm="region.osm.pbf",
                          poly_file="region.poly"):
    gdf = ox.geocode_to_gdf(region_name)
    geom = gdf.geometry.values[0]

    shapely_polygon_to_polyfile(geom, poly_file)

    cmd = [
        "osmconvert",
        osm_input_path,
        f"-B={poly_file}",
        f"-o={output_osm}"
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"Saved cut map to {output_osm}")
    except subprocess.CalledProcessError as e:
        print(f"Error running osmconvert: {e}")



def main(args=None):
    parser = argparse.ArgumentParser(description="Download and cut OSM data for a region.")

    parser.add_argument("--region", type=str, default="Ho Chi Minh City, Vietnam",
                        help="Tên khu vực để lấy polygon")
    parser.add_argument("--input", type=str, default="vietnam-latest.osm.pbf",
                        help="Đường dẫn đến file .osm.pbf đầu vào")
    parser.add_argument("--output", type=str, default="hochiminh.osm.pbf",
                        help="Đường dẫn file .osm.pbf đầu ra sau khi cắt")
    parser.add_argument("--poly", type=str, default="hochiminh.poly",
                        help="Tên file .poly để lưu vùng polygon")

    if isinstance(args, list):
        parsed_args = parser.parse_args(args)
    else:
        parsed_args = parser.parse_args() if args is None else parser.parse_args([])

    get_polygon_from_osm(
        region_name=parsed_args.region,
        osm_input_path=parsed_args.input,
        output_osm=parsed_args.output,
        poly_file=parsed_args.poly
    )


if __name__ == "__main__":
    main()