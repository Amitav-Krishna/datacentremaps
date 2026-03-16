#!/usr/bin/env python3
"""
Upload merged map artifacts to an S3-compatible bucket (Railway Object Storage).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import boto3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload map artifacts to object storage.")
    parser.add_argument("--bucket", default=os.environ.get("BUCKET"))
    parser.add_argument("--endpoint", default=os.environ.get("ENDPOINT"))
    parser.add_argument("--access-key-id", default=os.environ.get("ACCESS_KEY_ID"))
    parser.add_argument("--secret-access-key", default=os.environ.get("SECRET_ACCESS_KEY"))
    parser.add_argument("--region", default=os.environ.get("REGION", "auto"))
    parser.add_argument(
        "--merged-geojson-gz",
        default="data/boundaries/current/l2_scored_merged_simplified.geojson.gz",
        help="Local gzipped merged GeoJSON path.",
    )
    parser.add_argument(
        "--manifest",
        default="data/boundaries/current/l2_scored_manifest.json",
        help="Local merged manifest path.",
    )
    parser.add_argument(
        "--transmission-geojson",
        default="data/transmission_lines.geojson",
        help="Optional local transmission lines GeoJSON path.",
    )
    parser.add_argument(
        "--boundary-key",
        default="boundaries/current/l2_scored_merged_simplified.geojson.gz",
        help="Bucket key for merged boundary artifact.",
    )
    parser.add_argument(
        "--manifest-key",
        default="boundaries/current/l2_scored_manifest.json",
        help="Bucket key for merged manifest artifact.",
    )
    parser.add_argument(
        "--transmission-key",
        default="layers/transmission_lines.geojson",
        help="Bucket key for transmission lines artifact.",
    )
    parser.add_argument(
        "--skip-transmission",
        action="store_true",
        help="Skip uploading transmission lines artifact.",
    )
    return parser.parse_args()


def require_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def main() -> None:
    args = parse_args()
    if not all([args.bucket, args.endpoint, args.access_key_id, args.secret_access_key]):
        raise RuntimeError(
            "Missing bucket credentials. Required: BUCKET, ENDPOINT, ACCESS_KEY_ID, SECRET_ACCESS_KEY."
        )

    merged_path = Path(args.merged_geojson_gz)
    manifest_path = Path(args.manifest)
    transmission_path = Path(args.transmission_geojson)
    require_exists(merged_path, "Merged GeoJSON gzip")
    require_exists(manifest_path, "Manifest")
    if not args.skip_transmission:
        require_exists(transmission_path, "Transmission GeoJSON")

    client = boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        aws_access_key_id=args.access_key_id,
        aws_secret_access_key=args.secret_access_key,
        region_name=args.region,
    )

    client.upload_file(
        str(merged_path),
        args.bucket,
        args.boundary_key,
        ExtraArgs={
            "ContentType": "application/geo+json",
            "ContentEncoding": "gzip",
            "CacheControl": "public, max-age=300, stale-while-revalidate=86400",
        },
    )
    print(f"uploaded {merged_path} -> s3://{args.bucket}/{args.boundary_key}")

    client.upload_file(
        str(manifest_path),
        args.bucket,
        args.manifest_key,
        ExtraArgs={
            "ContentType": "application/json",
            "CacheControl": "public, max-age=60",
        },
    )
    print(f"uploaded {manifest_path} -> s3://{args.bucket}/{args.manifest_key}")

    if not args.skip_transmission:
        client.upload_file(
            str(transmission_path),
            args.bucket,
            args.transmission_key,
            ExtraArgs={
                "ContentType": "application/geo+json",
                "CacheControl": "public, max-age=300, stale-while-revalidate=86400",
            },
        )
        print(f"uploaded {transmission_path} -> s3://{args.bucket}/{args.transmission_key}")


if __name__ == "__main__":
    main()
