from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.routers.boundaries import router as boundaries_router
from backend.app.routers.transmission import router as transmission_router
from backend.app.services.artifacts import get_counties_payload
from backend.app.settings import get_settings

settings = get_settings()
app = FastAPI(title="Datacentre Maps API")

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin] if settings.frontend_origin != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(boundaries_router)
app.include_router(transmission_router)

if settings.frontend_dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=settings.frontend_dist_dir / "assets"), name="assets")


@app.get("/api/health")
def health() -> dict[str, str]:
    cache = get_counties_payload()
    return {"status": "ok", "data_source": cache["source"]}


def _spa_index() -> Path:
    return settings.frontend_dist_dir / "index.html"


@app.get("/")
def spa_root():
    index = _spa_index()
    if index.exists():
        return FileResponse(index)
    return {
        "status": "backend_ready",
        "message": "Frontend not built yet. Build frontend/ and copy dist/ for SPA serving.",
    }


@app.get("/{path:path}")
def spa_fallback(path: str):
    if path.startswith("api/"):
        return {"status": "not_found"}
    index = _spa_index()
    if index.exists():
        return FileResponse(index)
    return {"status": "not_found", "path": path}
