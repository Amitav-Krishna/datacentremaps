# Railway Deployment Runbook

## 1) Build US scoring artifact

```bash
python3 scripts/build_us_counties_scores.py
```

Inputs default to `data/raw/*` and outputs to `data/derived/*`.

## 2) Build merged + simplified boundary artifacts

```bash
python3 scripts/build_merged_boundaries.py
```

This writes:
- `data/boundaries/current/l2_scored_merged.geojson(.gz)`
- `data/boundaries/current/l2_scored_merged_simplified.geojson(.gz)`
- `data/boundaries/current/l2_scored_manifest.json`

## 3) Upload artifacts to Railway Object Storage

```bash
python3 scripts/upload_artifacts_to_bucket.py
```

The script reads bucket credentials from env vars:
- `ENDPOINT`
- `ACCESS_KEY_ID`
- `SECRET_ACCESS_KEY`
- `BUCKET`
- `REGION` (defaults to `auto`)

## 4) Railway service variables

Copy from `.env.railway.example` and set values in Railway:

- `USE_BUCKET_DATA=1`
- `BOUNDARY_MERGED_KEY=boundaries/current/l2_scored_merged_simplified.geojson.gz`
- `BOUNDARY_MANIFEST_KEY=boundaries/current/l2_scored_manifest.json`
- `TRANSMISSION_KEY=layers/transmission_lines.geojson`

## 5) Build/deploy

- Docker deployment uses the root `Dockerfile`.
- FastAPI entrypoint: `backend.app.main:app`
- Health endpoint: `/api/health`
