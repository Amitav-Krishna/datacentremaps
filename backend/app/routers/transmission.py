from __future__ import annotations

from typing import Any, Annotated, Optional

from fastapi import APIRouter, Query

from backend.app.services.artifacts import get_transmission_features

router = APIRouter(prefix="/api", tags=["transmission"])


def _in_bbox(feature: dict[str, Any], west: float, south: float, east: float, north: float) -> bool:
    geometry = feature.get("geometry", {})
    coords = geometry.get("coordinates", [])
    if geometry.get("type") == "MultiLineString" and coords:
        coords = coords[0]
    if not coords:
        return False
    lon, lat = coords[0]
    return west <= lon <= east and south <= lat <= north


@router.get("/transmission")
def transmission(
    bbox: Annotated[Optional[str], Query(description="west,south,east,north")] = None,
) -> dict[str, Any]:
    features = get_transmission_features()
    if bbox:
        west, south, east, north = [float(item) for item in bbox.split(",")]
        features = [feature for feature in features if _in_bbox(feature, west, south, east, north)]

    sorted_features = sorted(
        features,
        key=lambda feature: feature.get("properties", {}).get("length", 0),
        reverse=True,
    )[:1000]
    return {"type": "FeatureCollection", "features": sorted_features}
