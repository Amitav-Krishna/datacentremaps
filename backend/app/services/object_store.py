from __future__ import annotations

from functools import lru_cache

import boto3

from backend.app.settings import get_settings


@lru_cache(maxsize=1)
def get_bucket_client():
    settings = get_settings()
    if not (settings.endpoint and settings.access_key_id and settings.secret_access_key):
        return None
    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name=settings.region,
    )
