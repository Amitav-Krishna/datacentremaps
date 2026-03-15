#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SOURCES = (
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


def write_outputs(merged_geojson, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    merged_path = output_dir / "l2_scored_merged.geojson"
    manifest_path = output_dir / "l2_scored_manifest.json"

    merged_text = json.dumps(merged_geojson, separators=(",", ":"), ensure_ascii=False)
    merged_path.write_text(merged_text, encoding="utf-8")

    digest = hashlib.sha256(merged_text.encode("utf-8")).hexdigest()
    features = merged_geojson.get("features", [])
    manifest = {
        "artifact": str(merged_path).replace("\\", "/"),
        "feature_count": len(features),
        "bbox": bbox_for_features(features),
        "sha256": digest,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return merged_path, manifest_path, manifest


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
    return parser.parse_args()


def main():
    args = parse_args()
    source_paths = [Path(p) for p in args.sources]
    missing = [str(p) for p in source_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing source files: {missing}")

    merged = merge_feature_collections(source_paths)
    merged_path, manifest_path, manifest = write_outputs(merged, Path(args.output_dir))
    print(f"wrote {merged_path}")
    print(f"wrote {manifest_path}")
    print(f"feature_count={manifest['feature_count']}")
    print(f"sha256={manifest['sha256']}")


if __name__ == "__main__":
    main()
