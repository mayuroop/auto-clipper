import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from clipping.config import _make_url_slug, build_config
from clipping.engine import download_video, _finalize_interrupted_live_download
import web.api.app


def test_make_url_slug_live_and_shorts():
    slug_watch = _make_url_slug("https://www.youtube.com/watch?v=1234567890a", 0)
    slug_live = _make_url_slug("https://www.youtube.com/live/1234567890a", 0)
    slug_short = _make_url_slug("https://www.youtube.com/shorts/1234567890a", 0)
    slug_youtu = _make_url_slug("https://youtu.be/1234567890a", 0)

    assert slug_watch == "video_1_1234567890a"
    assert slug_live == "video_1_1234567890a"
    assert slug_short == "video_1_1234567890a"
    assert slug_youtu == "video_1_1234567890a"


def test_upcoming_live_stream_rejected():
    with patch("clipping.engine.YoutubeDL") as mock_ydl_cls:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {
            "live_status": "is_upcoming",
            "is_live": False,
        }
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        with pytest.raises(RuntimeError) as exc_info:
            download_video(
                url="https://www.youtube.com/watch?v=dummyupcoming",
                output_path="test_out.mp4",
                source_platform="youtube",
            )
        assert "upcoming" in str(exc_info.value).lower()


def test_fastapi_studio_and_root_redirect():
    client = TestClient(web.api.app.app)

    # API JSON request to root
    res_json = client.get("/", headers={"Accept": "application/json"})
    assert res_json.status_code == 200
    data = res_json.json()
    assert data["name"] == "OpenSource Clipping Studio"
    assert data["studio"] == "/studio/"

    # Browser HTML request to root
    res_html = client.get("/", headers={"Accept": "text/html"}, follow_redirects=False)
    assert res_html.status_code == 307
    assert res_html.headers["location"] == "/studio/"

    # Access static studio
    res_studio = client.get("/studio/", follow_redirects=True)
    assert res_studio.status_code == 200
    assert "<title" in res_studio.text.lower()

