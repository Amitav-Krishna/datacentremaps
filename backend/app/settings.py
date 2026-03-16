from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    use_bucket_data: bool
    endpoint: Optional[str]
    access_key_id: Optional[str]
    secret_access_key: Optional[str]
    region: str
    bucket: Optional[str]
    boundary_merged_key: str
    boundary_manifest_key: str
    transmission_key: str
    local_merged_path: Path
    local_manifest_path: Path
    local_transmission_path: Path
    frontend_dist_dir: Path
    frontend_origin: str


def _read_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[2]
    return Settings(
        base_dir=base_dir,
        use_bucket_data=_read_bool_env("USE_BUCKET_DATA", True),
        endpoint=os.environ.get("ENDPOINT"),
        access_key_id=os.environ.get("ACCESS_KEY_ID"),
        secret_access_key=os.environ.get("SECRET_ACCESS_KEY"),
        region=os.environ.get("REGION", "auto"),
        bucket=os.environ.get("BUCKET"),
        boundary_merged_key=os.environ.get(
            "BOUNDARY_MERGED_KEY", "boundaries/current/l2_scored_merged_simplified.geojson.gz"
        ),
        boundary_manifest_key=os.environ.get(
            "BOUNDARY_MANIFEST_KEY", "boundaries/current/l2_scored_manifest.json"
        ),
        transmission_key=os.environ.get("TRANSMISSION_KEY", "layers/transmission_lines.geojson"),
        local_merged_path=base_dir
        / "data"
        / "boundaries"
        / "current"
        / "l2_scored_merged_simplified.geojson",
        local_manifest_path=base_dir / "data" / "boundaries" / "current" / "l2_scored_manifest.json",
        local_transmission_path=base_dir / "data" / "transmission_lines.geojson",
        frontend_dist_dir=base_dir / "frontend" / "dist",
        frontend_origin=os.environ.get("FRONTEND_ORIGIN", "*"),
    )
