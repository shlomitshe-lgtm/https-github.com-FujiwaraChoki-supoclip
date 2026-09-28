from types import SimpleNamespace

import pytest

from src.services.youtube_publish_service import (
    YouTubeNotConnected,
    YouTubePublishError,
    YouTubePublishService,
    build_shorts_title,
    normalize_tags,
)


class FakeConnectedAccounts:
    def __init__(self, accounts):
        self.accounts = accounts
        self.list_calls = []
        self.link_calls = []
        self.deleted = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return SimpleNamespace(items=list(self.accounts))

    def link(self, user_id, auth_config_id, **kwargs):
        self.link_calls.append((user_id, auth_config_id, kwargs))
        return SimpleNamespace(redirect_url="https://connect.composio.dev/link/abc")

    def delete(self, account_id):
        self.deleted.append(account_id)


class FakeTools:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def execute(self, slug, arguments, **kwargs):
        self.calls.append((slug, arguments, kwargs))
        return self.result


class FakeComposio:
    def __init__(self, accounts=None, result=None):
        self.connected_accounts = FakeConnectedAccounts(accounts or [])
        self.tools = FakeTools(
            result
            or {"successful": True, "error": None, "data": {"response_data": {"id": "vid123"}}}
        )
        self.toolkits = SimpleNamespace(_get_auth_config_id=lambda toolkit: "ac_managed")


def make_service(client, auth_config_id=None):
    config = SimpleNamespace(
        composio_api_key="ck_test",
        composio_youtube_auth_config_id=auth_config_id,
    )
    return YouTubePublishService(config, client=client)


def test_build_shorts_title_appends_tag_and_respects_limit():
    assert build_shorts_title("  Big   idea ") == "Big idea #Shorts"
    assert build_shorts_title("Already #shorts") == "Already #shorts"
    assert len(build_shorts_title("x" * 300)) == 100
    assert build_shorts_title("").startswith("SupoClip Short")


def test_normalize_tags_dedupes_and_strips_hashes():
    assert normalize_tags("#ai, podcast, AI ,") == ["ai", "podcast"]
    assert normalize_tags(["one", 2, " two "]) == ["one", "two"]
    assert normalize_tags(None) == []


async def test_status_reports_not_configured_without_api_key():
    service = YouTubePublishService(
        SimpleNamespace(composio_api_key=None, composio_youtube_auth_config_id=None)
    )
    assert await service.get_status("user-1") == {"configured": False, "connected": False}


async def test_status_reports_connected_account():
    client = FakeComposio(accounts=[SimpleNamespace(id="ca_1", created_at="2026-09-01")])
    status = await make_service(client).get_status("user-1")

    assert status["connected"] is True
    assert status["connected_account_id"] == "ca_1"
    assert client.connected_accounts.list_calls[0]["user_ids"] == ["user-1"]
    assert client.connected_accounts.list_calls[0]["toolkit_slugs"] == ["youtube"]


async def test_connect_link_prefers_configured_auth_config():
    client = FakeComposio()
    url = await make_service(client, auth_config_id="ac_custom").create_connect_link(
        "user-1", "http://localhost:3107/settings"
    )

    assert url == "https://connect.composio.dev/link/abc"
    user_id, auth_config_id, kwargs = client.connected_accounts.link_calls[0]
    assert (user_id, auth_config_id) == ("user-1", "ac_custom")
    assert kwargs["callback_url"] == "http://localhost:3107/settings"


async def test_publish_requires_connection(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")

    with pytest.raises(YouTubeNotConnected):
        await make_service(FakeComposio()).publish_clip("user-1", clip, title="Hi")


async def test_publish_uploads_clip_and_returns_shorts_url(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    client = FakeComposio(accounts=[SimpleNamespace(id="ca_1")])

    result = await make_service(client).publish_clip(
        "user-1", clip, title="Hook", tags="a,b", privacy_status="Unlisted"
    )

    assert result == {
        "video_id": "vid123",
        "url": "https://youtube.com/shorts/vid123",
        "privacy_status": "unlisted",
    }
    slug, arguments, kwargs = client.tools.calls[0]
    assert slug == "YOUTUBE_UPLOAD_VIDEO"
    assert arguments["title"] == "Hook #Shorts"
    assert arguments["tags"] == ["a", "b"]
    assert arguments["categoryId"] == "22"
    assert arguments["videoFilePath"] == str(clip.resolve())
    assert kwargs["user_id"] == "user-1"
    assert kwargs["connected_account_id"] == "ca_1"


async def test_publish_surfaces_composio_failure(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    client = FakeComposio(
        accounts=[SimpleNamespace(id="ca_1")],
        result={"successful": False, "error": "quotaExceeded", "data": {}},
    )

    with pytest.raises(YouTubePublishError, match="quotaExceeded"):
        await make_service(client).publish_clip("user-1", clip, title="Hook")


async def test_publish_rejects_invalid_privacy(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")

    with pytest.raises(ValueError):
        await make_service(FakeComposio()).publish_clip(
            "user-1", clip, title="Hook", privacy_status="secret"
        )
