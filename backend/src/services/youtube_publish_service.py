"""
Publish clips to YouTube (Shorts) through Composio.

Composio hosts the Google OAuth flow and stores each user's YouTube
connection, keyed by the SupoClip user id. SupoClip never sees the Google
tokens: it asks Composio for a connect link, and later asks Composio to run
the ``YOUTUBE_UPLOAD_VIDEO`` tool on the user's behalf.

The Composio SDK is synchronous, so every call is wrapped in ``run_in_thread``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.async_helpers import run_in_thread

logger = logging.getLogger(__name__)

YOUTUBE_TOOLKIT = "youtube"
UPLOAD_TOOL = "YOUTUBE_UPLOAD_VIDEO"
VALID_PRIVACY_STATUSES = {"public", "private", "unlisted"}
# 22 = "People & Blogs", YouTube's generic default category.
DEFAULT_CATEGORY_ID = "22"
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 5000
MAX_TAGS = 30


class YouTubePublishError(Exception):
    """Raised when Composio reports a failure we should surface to the user."""


class YouTubeNotConfigured(YouTubePublishError):
    """Raised when COMPOSIO_API_KEY is missing."""


class YouTubeNotConnected(YouTubePublishError):
    """Raised when the user has no active YouTube connection."""


def build_shorts_title(title: str) -> str:
    """Trim to YouTube's 100-char limit and tag the upload as a Short."""
    cleaned = " ".join((title or "").split()) or "SupoClip Short"
    suffix = " #Shorts"
    if "#shorts" in cleaned.lower():
        return cleaned[:MAX_TITLE_LENGTH]
    return cleaned[: MAX_TITLE_LENGTH - len(suffix)].rstrip() + suffix


def normalize_tags(tags: Any) -> List[str]:
    if isinstance(tags, str):
        tags = tags.split(",")
    if not isinstance(tags, list):
        return []
    normalized: List[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        value = tag.strip().lstrip("#").strip()
        if value and value.lower() not in {t.lower() for t in normalized}:
            normalized.append(value[:100])
    return normalized[:MAX_TAGS]


def _extract_video_id(data: Any) -> Optional[str]:
    """Find the uploaded video id in Composio's response payload."""
    if not isinstance(data, dict):
        return None
    for key in ("id", "video_id", "videoId"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    for key in ("response_data", "data", "video", "response"):
        found = _extract_video_id(data.get(key))
        if found:
            return found
    return None


class YouTubePublishService:
    def __init__(self, config: Config, client: Any = None):
        self.config = config
        self._client = client

    @property
    def is_configured(self) -> bool:
        return bool(self.config.composio_api_key) or self._client is not None

    def _get_client(self, upload_dir: Optional[Path] = None):
        if self._client is not None:
            return self._client
        if not self.config.composio_api_key:
            raise YouTubeNotConfigured(
                "YouTube publishing is not configured. Set COMPOSIO_API_KEY."
            )
        from composio import Composio

        kwargs: Dict[str, Any] = {"api_key": self.config.composio_api_key}
        if upload_dir is not None:
            # Let the SDK upload the local clip file to Composio's storage, but
            # only from the directory holding this one clip.
            kwargs["dangerously_allow_auto_upload_download_files"] = True
            kwargs["file_upload_dirs"] = [str(upload_dir.resolve())]
        return Composio(**kwargs)

    # ------------------------------------------------------------------ status

    def _list_active_accounts_sync(self, user_id: str) -> List[Any]:
        client = self._get_client()
        response = client.connected_accounts.list(
            user_ids=[user_id],
            toolkit_slugs=[YOUTUBE_TOOLKIT],
            statuses=["ACTIVE"],
        )
        return list(getattr(response, "items", None) or [])

    async def get_status(self, user_id: str) -> Dict[str, Any]:
        if not self.is_configured:
            return {"configured": False, "connected": False}
        accounts = await run_in_thread(self._list_active_accounts_sync, user_id)
        if not accounts:
            return {"configured": True, "connected": False}
        account = accounts[0]
        created_at = getattr(account, "created_at", None)
        return {
            "configured": True,
            "connected": True,
            "connected_account_id": getattr(account, "id", None),
            "connected_at": str(created_at) if created_at else None,
        }

    # ----------------------------------------------------------------- connect

    def _connect_sync(self, user_id: str, callback_url: Optional[str]) -> str:
        client = self._get_client()
        auth_config_id = self.config.composio_youtube_auth_config_id
        if not auth_config_id:
            # Falls back to (or creates) a Composio-managed OAuth auth config.
            auth_config_id = client.toolkits._get_auth_config_id(toolkit=YOUTUBE_TOOLKIT)
        request = client.connected_accounts.link(
            user_id,
            auth_config_id,
            callback_url=callback_url,
            allow_multiple=True,
        )
        redirect_url = getattr(request, "redirect_url", None)
        if not redirect_url:
            raise YouTubePublishError("Composio did not return a connect link")
        return redirect_url

    async def create_connect_link(
        self, user_id: str, callback_url: Optional[str] = None
    ) -> str:
        return await run_in_thread(self._connect_sync, user_id, callback_url)

    def _disconnect_sync(self, user_id: str) -> int:
        client = self._get_client()
        removed = 0
        for account in self._list_active_accounts_sync(user_id):
            client.connected_accounts.delete(account.id)
            removed += 1
        return removed

    async def disconnect(self, user_id: str) -> int:
        return await run_in_thread(self._disconnect_sync, user_id)

    # ----------------------------------------------------------------- publish

    def _publish_sync(
        self,
        user_id: str,
        clip_path: Path,
        title: str,
        description: str,
        tags: List[str],
        privacy_status: str,
        category_id: str,
    ) -> Dict[str, Any]:
        client = self._get_client(upload_dir=clip_path.parent)
        accounts = self._list_active_accounts_sync(user_id)
        if not accounts:
            raise YouTubeNotConnected("Connect your YouTube account first.")

        execute_kwargs: Dict[str, Any] = {
            "user_id": user_id,
            "connected_account_id": accounts[0].id,
        }
        toolkit_version = os.getenv("COMPOSIO_YOUTUBE_TOOLKIT_VERSION", "").strip()
        if toolkit_version:
            execute_kwargs["version"] = toolkit_version
        else:
            execute_kwargs["dangerously_skip_version_check"] = True

        result = client.tools.execute(
            UPLOAD_TOOL,
            {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
                "privacyStatus": privacy_status,
                "videoFilePath": str(clip_path.resolve()),
            },
            **execute_kwargs,
        )
        if not result.get("successful"):
            error = result.get("error") or "YouTube upload failed"
            raise YouTubePublishError(str(error))

        video_id = _extract_video_id(result.get("data"))
        return {
            "video_id": video_id,
            "url": f"https://youtube.com/shorts/{video_id}" if video_id else None,
            "privacy_status": privacy_status,
        }

    async def publish_clip(
        self,
        user_id: str,
        clip_path: Path,
        *,
        title: str,
        description: str = "",
        tags: Any = None,
        privacy_status: str = "private",
        category_id: str = DEFAULT_CATEGORY_ID,
    ) -> Dict[str, Any]:
        privacy = (privacy_status or "private").strip().lower()
        if privacy not in VALID_PRIVACY_STATUSES:
            raise ValueError(
                f"privacy_status must be one of: {', '.join(sorted(VALID_PRIVACY_STATUSES))}"
            )
        category = str(category_id or DEFAULT_CATEGORY_ID).strip()
        if not category.isdigit():
            raise ValueError("category_id must be a numeric YouTube category id")

        return await run_in_thread(
            self._publish_sync,
            user_id,
            clip_path,
            build_shorts_title(title),
            (description or "")[:MAX_DESCRIPTION_LENGTH],
            normalize_tags(tags),
            privacy,
            category,
        )
