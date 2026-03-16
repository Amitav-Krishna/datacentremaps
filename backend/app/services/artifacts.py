from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from backend.app.services.object_store import get_bucket_client
from backend.app.settings import get_settings

logger = logging.getLogger(__name__)


def _read_bytes(path: Path) -> bytes:
    with path.open("rb") as f:
        return f.read()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
        if not isinstance(value, dict):
            raise ValueError(f"Expected object JSON in {path}")
        return value


def _load_from_bucket(key: str) -> bytes:
    settings = get_settings()
    client = get_bucket_client()
    if client is None or not settings.bucket:
        raise RuntimeError("Bucket credentials are not configured.")
    response = client.get_object(Bucket=settings.bucket, Key=key)
    return response["Body"].read()


@lru_cache(maxsize=1)
def get_manifest_data() -> dict[str, Any]:
    settings = get_settings()
    if settings.use_bucket_data:
        try:
            payload = _load_from_bucket(settings.boundary_manifest_key)
            manifest = json.loads(payload.decode("utf-8"))
            if isinstance(manifest, dict):
                return manifest
        except Exception as exc:  # pragma: no cover - defensive fallback path
            logger.warning("Bucket manifest load failed (%s), falling back to local.", exc)

    if settings.local_manifest_path.exists():
        return _read_json(settings.local_manifest_path)
    return {}


@lru_cache(maxsize=1)
def get_counties_payload() -> dict[str, Any]:
    settings = get_settings()
    payload: Optional[bytes] = None
    source: str = "local"
    content_encoding: Optional[str] = None

    if settings.use_bucket_data:
        try:
            payload = _load_from_bucket(settings.boundary_merged_key)
            source = f"bucket:{settings.boundary_merged_key}"
            if settings.boundary_merged_key.endswith(".gz"):
                content_encoding = "gzip"
        except Exception as exc:  # pragma: no cover - defensive fallback path
            logger.warning("Bucket merged payload load failed (%s), falling back to local.", exc)

    if payload is None:
        local_path = settings.local_merged_path
        if not local_path.exists():
            local_path = settings.base_dir / "data" / "boundaries" / "current" / "l2_scored_merged.geojson"
        payload = _read_bytes(local_path)
        source = f"local:{local_path}"
        if local_path.name.endswith(".gz"):
            content_encoding = "gzip"

    manifest = get_manifest_data()
    digest = manifest.get("sha256")
    if not isinstance(digest, str) or not digest:
        digest = hashlib.sha256(payload).hexdigest()
    etag = f"\"{digest}\""
    feature_count = manifest.get("feature_count")
    if not isinstance(feature_count, int):
        feature_count = 0

    logger.info("Loaded counties payload source=%s features=%s", source, feature_count)
    return {
        "payload": payload,
        "etag": etag,
        "source": source,
        "feature_count": feature_count,
        "content_encoding": content_encoding,
    }


@lru_cache(maxsize=1)
def get_transmission_features() -> list[dict[str, Any]]:
    settings = get_settings()
    payload: Optional[bytes] = None

    if settings.use_bucket_data:
        try:
            payload = _load_from_bucket(settings.transmission_key)
        except Exception as exc:  # pragma: no cover - defensive fallback path
            logger.warning("Bucket transmission load failed (%s), falling back to local.", exc)

    if payload is None:
        payload = _read_bytes(settings.local_transmission_path)

    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, dict):
        return []
    features = decoded.get("features", [])
    return features if isinstance(features, list) else []
