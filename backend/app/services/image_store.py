"""Prescription image storage — uploads prescription images to S3 for debugging and audit.

Images are stored under the `prescriptions/` prefix with a 30-day lifecycle rule.
Uses the same S3 bucket as TTS audio storage.
"""

from __future__ import annotations

from asyncio import to_thread as asyncio_to_thread
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from loguru import logger

# ---------------------------------------------------------------------------
# Lazy S3 client singleton (shared pattern with tts.py)
# ---------------------------------------------------------------------------

_s3_client = None


def _get_s3_client():
    """Return a reusable boto3 S3 client (lazy-initialized singleton)."""
    global _s3_client
    if _s3_client is None:
        from backend.app.core.config import settings

        kwargs = {
            "service_name": "s3",
            "region_name": "ap-south-1",
            "config": Config(signature_version="s3v4"),
        }
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        _s3_client = boto3.client(**kwargs)
    return _s3_client


def _reset_s3_client() -> None:
    """Clear the S3 client singleton (for testing)."""
    global _s3_client
    _s3_client = None


# ---------------------------------------------------------------------------
# Content-type to extension mapping
# ---------------------------------------------------------------------------

_EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ImageStoreError(Exception):
    """Raised on any image storage failure."""


async def store_prescription_image(
    image_bytes: bytes,
    request_id: str,
    content_type: str = "image/jpeg",
) -> str:
    """Upload a prescription image to S3 and return the object key.

    Stores under `prescriptions/{request_id}/{uuid}.{ext}`.
    The 30-day lifecycle rule on the `prescriptions/` prefix handles cleanup.

    Returns the S3 object key (not a URL — images are never served to users).
    Raises ImageStoreError on S3 failures.
    Raises ValueError on empty image_bytes.
    """
    if not image_bytes:
        raise ValueError("image_bytes must be non-empty")

    ext = _EXTENSION_MAP.get(content_type, ".jpg")
    key = f"prescriptions/{request_id}/{uuid4()}{ext}"

    s3 = _get_s3_client()
    from backend.app.core.config import settings

    logger.info(
        "Storing prescription image | request_id={} | key={} | size={}",
        request_id,
        key,
        len(image_bytes),
    )

    try:
        await asyncio_to_thread(
            lambda: s3.put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=image_bytes,
                ContentType=content_type,
                Metadata={"request-id": request_id},
            )
        )
    except (ClientError, Exception) as exc:
        logger.error(
            "Prescription image upload failed | request_id={} | key={} | error={}",
            request_id,
            key,
            type(exc).__name__,
        )
        raise ImageStoreError(f"S3 put_object failed: {exc}") from exc

    logger.info(
        "Prescription image stored | request_id={} | key={}",
        request_id,
        key,
    )

    return key
