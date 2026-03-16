#!/usr/bin/env python3
import argparse
import copy
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SOURCES = (
    "data/derived/us_counties_scored.geojson",
    "data/boundaries/can_scored.geojson",
    "data/boundaries/chn_scored.geojson",
    "data/boundaries/mex_scored.geojson",
)


def merge_feature_collections(source_paths):
    merged_features = []
    for path in source_paths:
        with path.open("r", encoding="utf-8") as f:
            geojson = json.load(f)
        merged_features.extend(geojson.get("features", []))
    return {"type": "FeatureCollection", "features": merged_features}


def bbox_for_features(features):
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    def scan_coords(coords):
        nonlocal min_x, min_y, max_x, max_y
        if isinstance(coords, (list, tuple)):
            if coords and isinstance(coords[0], (int, float)) and len(coords) >= 2:
                x, y = float(coords[0]), float(coords[1])
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
            else:
                for item in coords:
                    scan_coords(item)

    for feature in features:
        geometry = feature.get("geometry") or {}
        scan_coords(geometry.get("coordinates"))

    if min_x == float("inf"):
        return None
    return [min_x, min_y, max_x, max_y]


def simplify_geojson(geojson, simplify_step):
    if simplify_step <= 1:
        return geojson

    def is_point(value):
        return (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        )

    def decimate_line(line):
        if len(line) <= 4:
            return line
        reduced = [line[0]]
        for idx in range(1, len(line) - 1):
            if idx % simplify_step == 0:
                reduced.append(line[idx])
        reduced.append(line[-1])
        return reduced if len(reduced) >= 2 else line

    def decimate_coords(coords):
        if not isinstance(coords, list) or not coords:
            return coords
        if is_point(coords):
            return coords
        if is_point(coords[0]):
            return decimate_line(coords)
        return [decimate_coords(item) for item in coords]

    simplified = copy.deepcopy(geojson)
    for feature in simplified.get("features", []):
        geometry = feature.get("geometry") or {}
        if "coordinates" in geometry:
            geometry["coordinates"] = decimate_coords(geometry["coordinates"])
    return simplified


def write_outputs(merged_geojson, simplified_geojson, output_dir, source_paths, write_gzip):
    output_dir.mkdir(parents=True, exist_ok=True)
    merged_path = output_dir / "l2_scored_merged.geojson"
    merged_gzip_path = output_dir / "l2_scored_merged.geojson.gz"
    merged_simplified_path = output_dir / "l2_scored_merged_simplified.geojson"
    merged_simplified_gzip_path = output_dir / "l2_scored_merged_simplified.geojson.gz"
    manifest_path = output_dir / "l2_scored_manifest.json"

    merged_text = json.dumps(merged_geojson, separators=(",", ":"), ensure_ascii=False)
    merged_path.write_text(merged_text, encoding="utf-8")
    merged_bytes = merged_text.encode("utf-8")

    simplified_text = json.dumps(simplified_geojson, separators=(",", ":"), ensure_ascii=False)
    merged_simplified_path.write_text(simplified_text, encoding="utf-8")
    simplified_bytes = simplified_text.encode("utf-8")

    if write_gzip:
        with gzip.open(merged_gzip_path, "wb", compresslevel=6) as gz_file:
            gz_file.write(merged_bytes)
        with gzip.open(merged_simplified_gzip_path, "wb", compresslevel=6) as gz_file:
            gz_file.write(simplified_bytes)

    digest = hashlib.sha256(merged_bytes).hexdigest()
    features = merged_geojson.get("features", [])
    manifest = {
        "artifact": str(merged_path).replace("\\", "/"),
        "artifact_gzip": str(merged_gzip_path).replace("\\", "/") if write_gzip else None,
        "artifact_simplified": str(merged_simplified_path).replace("\\", "/"),
        "artifact_simplified_gzip": (
            str(merged_simplified_gzip_path).replace("\\", "/") if write_gzip else None
        ),
        "feature_count": len(features),
        "bbox": bbox_for_features(features),
        "sha256": digest,
        "sha256_simplified": hashlib.sha256(simplified_bytes).hexdigest(),
        "bytes_raw": len(merged_bytes),
        "bytes_raw_simplified": len(simplified_bytes),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [str(p).replace("\\", "/") for p in source_paths],
    }
    if write_gzip:
        manifest["bytes_gzip"] = merged_gzip_path.stat().st_size
        manifest["bytes_gzip_simplified"] = merged_simplified_gzip_path.stat().st_size

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return (
        merged_path,
        merged_gzip_path,
        merged_simplified_path,
        merged_simplified_gzip_path,
        manifest_path,
        manifest,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Build merged scored boundaries artifact.")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=list(DEFAULT_SOURCES),
        help="Source GeoJSON files to merge.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/boundaries/current",
        help="Directory to write merged artifact and manifest.",
    )
    parser.add_argument(
        "--no-gzip",
        action="store_true",
        help="Do not write .geojson.gz output.",
    )
    parser.add_argument(
        "--simplify-step",
        type=int,
        default=3,
        help="Coordinate decimation step for simplified artifact (1 disables).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    source_paths = [Path(p) for p in args.sources]
    missing = [str(p) for p in source_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing source files: {missing}")

    merged = merge_feature_collections(source_paths)
    simplified = simplify_geojson(merged, max(1, args.simplify_step))
    (
        merged_path,
        merged_gzip_path,
        merged_simplified_path,
        merged_simplified_gzip_path,
        manifest_path,
        manifest,
    ) = write_outputs(
        merged_geojson=merged,
        simplified_geojson=simplified,
        output_dir=Path(args.output_dir),
        source_paths=source_paths,
        write_gzip=not args.no_gzip,
    )
    print(f"wrote {merged_path}")
    print(f"wrote {merged_simplified_path}")
    if not args.no_gzip:
        print(f"wrote {merged_gzip_path}")
        print(f"wrote {merged_simplified_gzip_path}")
    print(f"wrote {manifest_path}")
    print(f"feature_count={manifest['feature_count']}")
    print(f"sha256={manifest['sha256']}")


if __name__ == "__main__":
    main()
