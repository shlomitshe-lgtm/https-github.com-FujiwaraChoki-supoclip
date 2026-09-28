"""
Third-party account integrations (currently: YouTube via Composio).

Connecting and disconnecting accounts is authenticated with the frontend's
signed session headers only, so a leaked API key cannot attach someone else's
YouTube channel. Publishing itself lives on the tasks router.
"""

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request

from ...auth_headers import get_authenticated_user_id
from ...config import get_config
from ...services.youtube_publish_service import (
    YouTubeNotConfigured,
    YouTubePublishService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


def _get_user_id(request: Request) -> str:
    return get_authenticated_user_id(request, get_config())


def _safe_callback_url(value: object) -> str:
    """Only allow redirects back to our own app after the OAuth flow."""
    config = get_config()
    default = f"{config.app_base_url}/settings?youtube=connected"
    if not isinstance(value, str) or not value.strip():
        return default
    candidate = urlparse(value.strip())
    allowed = urlparse(config.app_base_url)
    if (candidate.scheme, candidate.netloc) != (allowed.scheme, allowed.netloc):
        return default
    return value.strip()


@router.get("/youtube")
async def get_youtube_status(request: Request):
    """Return whether publishing is configured and the user's channel is connected."""
    user_id = _get_user_id(request)
    service = YouTubePublishService(get_config())
    try:
        return await service.get_status(user_id)
    except Exception as exc:
        logger.error("Failed to read YouTube connection status: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach Composio")


@router.post("/youtube/connect")
async def connect_youtube(request: Request):
    """Start the Composio-hosted Google OAuth flow; returns the URL to open."""
    user_id = _get_user_id(request)
    try:
        payload = await request.json()
    except ValueError:
        payload = {}
    callback_url = _safe_callback_url(
        payload.get("callback_url") if isinstance(payload, dict) else None
    )

    service = YouTubePublishService(get_config())
    try:
        redirect_url = await service.create_connect_link(user_id, callback_url)
    except YouTubeNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to create YouTube connect link: %s", exc)
        raise HTTPException(status_code=502, detail="Could not start YouTube connection")
    return {"redirect_url": redirect_url}


@router.delete("/youtube")
async def disconnect_youtube(request: Request):
    """Remove the user's YouTube connection from Composio."""
    user_id = _get_user_id(request)
    service = YouTubePublishService(get_config())
    try:
        removed = await service.disconnect(user_id)
    except YouTubeNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to disconnect YouTube: %s", exc)
        raise HTTPException(status_code=502, detail="Could not disconnect YouTube")
    return {"disconnected": removed > 0}
