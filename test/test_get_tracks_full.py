"""Integration tests for SoundCloudAPI — full-metadata track listing and search.

SoundCloudAPI uses SoundCloud's internal API v2 to paginate through an artist or
set page with full metadata (display name, artwork, duration).  Unlike
SoundCloudHTML which is capped at ~20 items, get_tracks() paginates the complete
catalogue.

These tests hit the real SoundCloud API — run selectively::

    pytest test/test_get_tracks_full.py -v -m integration
"""
import pytest
from nuvem_de_som import SoundCloud, SoundCloudAPI, SoundCloudHTML


ARTIST_URL = "https://soundcloud.com/acidkid"
# acidkid is the URL slug; the real display name returned by the API is "Piratech"
ARTIST_DISPLAY_NAME = "Piratech"
SET_URL = "https://soundcloud.com/acidkid/sets/beathop"


def _assert_full_track(track: dict) -> None:
    for key in ("title", "url", "artist", "artist_url", "image", "duration"):
        assert key in track, f"track missing expected key: {key!r}"
    assert track["url"].startswith("https://soundcloud.com/"), (
        f"unexpected url: {track['url']}"
    )


@pytest.mark.integration
def test_api_get_tracks_returns_tracks():
    sc = SoundCloudAPI()
    tracks = list(sc.get_tracks(ARTIST_URL, limit=50))
    assert len(tracks) > 0, "expected at least one track"
    for t in tracks:
        _assert_full_track(t)


@pytest.mark.integration
def test_api_get_tracks_more_than_html_scrape():
    """API pagination should yield at least as many tracks as HTML scraper."""
    html_tracks = list(SoundCloudHTML().get_tracks(ARTIST_URL))
    api_tracks = list(SoundCloudAPI().get_tracks(ARTIST_URL, limit=200))
    assert len(api_tracks) >= len(html_tracks), (
        f"expected api >= html: {len(api_tracks)} vs {len(html_tracks)}"
    )


@pytest.mark.integration
def test_api_get_tracks_real_artist_name():
    """API returns the display name, not the URL slug."""
    sc = SoundCloudAPI()
    tracks = list(sc.get_tracks(ARTIST_URL, limit=5))
    assert tracks, "no tracks returned"
    assert tracks[0]["artist"] == ARTIST_DISPLAY_NAME, (
        f"expected artist {ARTIST_DISPLAY_NAME!r}, got {tracks[0]['artist']!r}"
    )


@pytest.mark.integration
def test_api_get_tracks_has_artwork_and_duration():
    sc = SoundCloudAPI()
    tracks = list(sc.get_tracks(ARTIST_URL, limit=5))
    assert tracks, "no tracks returned"
    assert any(t["image"] for t in tracks), "expected at least one track with artwork"
    assert any(t["duration"] for t in tracks), "expected at least one track with duration"


@pytest.mark.integration
def test_api_get_tracks_set_url():
    sc = SoundCloudAPI()
    tracks = list(sc.get_tracks(SET_URL, limit=50))
    assert len(tracks) > 0, "expected at least one track in set"
    for t in tracks:
        _assert_full_track(t)


@pytest.mark.integration
def test_api_get_tracks_respects_limit():
    sc = SoundCloudAPI()
    limit = 10
    tracks = list(sc.get_tracks(ARTIST_URL, limit=limit))
    assert len(tracks) <= limit, (
        f"expected at most {limit} tracks, got {len(tracks)}"
    )


@pytest.mark.integration
def test_api_search_tracks_returns_full_metadata():
    sc = SoundCloudAPI()
    tracks = list(sc.search_tracks("nuclear chill", limit=5))
    assert len(tracks) > 0, "expected at least one result"
    for t in tracks:
        for key in ("title", "url", "artist", "artist_url", "image", "duration"):
            assert key in t, f"track missing key {key!r}"
        assert t["url"].startswith("https://soundcloud.com/"), f"bad url: {t['url']}"
    assert any(t["image"] for t in tracks), "expected at least one track with artwork"
    assert any(t["duration"] for t in tracks), "expected at least one track with duration"


@pytest.mark.integration
def test_api_search_people_returns_full_metadata():
    sc = SoundCloudAPI()
    people = list(sc.search_people("piratech", limit=5))
    assert len(people) > 0, "expected at least one result"
    for p in people:
        for key in ("artist", "artist_url", "image"):
            assert key in p, f"person missing key {key!r}"
        assert p["artist_url"].startswith("https://soundcloud.com/"), (
            f"bad url: {p['artist_url']}"
        )
    assert any(p["image"] for p in people), "expected at least one artist with image"


@pytest.mark.integration
def test_factory_auto_search_tracks():
    """SoundCloud() auto-backend should return full-metadata tracks via API."""
    sc = SoundCloud()
    tracks = list(sc.search_tracks("nuclear chill", limit=5))
    assert len(tracks) > 0
    for t in tracks:
        assert "title" in t and "url" in t


@pytest.mark.integration
def test_api_resolve_user():
    sc = SoundCloudAPI()
    info = sc.resolve_user(ARTIST_URL)
    assert info is not None, "resolve_user returned None"
    assert info["artist"] == ARTIST_DISPLAY_NAME, (
        f"expected {ARTIST_DISPLAY_NAME!r}, got {info['artist']!r}"
    )
    assert info["artist_url"].startswith("https://soundcloud.com/")
    assert info.get("user_id"), "resolve_user must surface the numeric user_id"
    assert isinstance(info["user_id"], int)


@pytest.mark.integration
def test_api_resolve_track():
    """A track URL must round-trip into the same dict shape as search_tracks."""
    sc = SoundCloudAPI()
    # Pick the first published track of the canonical test artist.
    tracks = list(sc.get_tracks(ARTIST_URL, limit=1))
    assert tracks, "no tracks for canonical artist; cannot test resolve_track"
    track_url = tracks[0]["url"]
    info = sc.resolve_track(track_url)
    assert info is not None, f"resolve_track returned None for {track_url}"
    for key in ("title", "url", "artist", "artist_url",
                "image", "duration", "track_id", "user_id"):
        assert key in info, f"resolve_track missing {key}"
    assert isinstance(info["track_id"], int)
    assert isinstance(info["user_id"], int)


@pytest.mark.integration
def test_api_resolve_track_returns_none_for_user_url():
    """A user permalink fed to resolve_track must return None, not a track dict."""
    sc = SoundCloudAPI()
    assert sc.resolve_track(ARTIST_URL) is None
