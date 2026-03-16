from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response

from backend.app.services.artifacts import get_counties_payload, get_manifest_data

router = APIRouter(prefix="/api", tags=["boundaries"])


@router.get("/counties")
def counties(request: Request) -> Response:
    cache = get_counties_payload()
    etag = cache["etag"]

    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304,
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=300, stale-while-revalidate=86400",
            },
        )

    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300, stale-while-revalidate=86400",
        "X-Feature-Count": str(cache["feature_count"]),
        "X-Data-Source": cache["source"],
    }
    if cache["content_encoding"]:
        headers["Content-Encoding"] = cache["content_encoding"]
    return Response(content=cache["payload"], media_type="application/json", headers=headers)


@router.get("/manifest")
def manifest() -> dict[str, Any]:
    data = get_manifest_data()
    return data if data else {"status": "manifest_unavailable"}
