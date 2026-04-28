"""Tests for SoundCloud.get_tracks_full().

get_tracks_full() uses SoundCloud's API v2 (client_id auto-managed by yt-dlp)
to paginate through an artist or set page.  Unlike get_tracks() — which scrapes
HTML and is capped at ~20 items — this method retrieves the complete catalogue
with full metadata: real artist display name, per-track artwork, and duration.

These tests are integration tests: they hit the real SoundCloud API, so they
require a live network connection and may be slow.  Run selectively with::

    pytest test/test_get_tracks_full.py -v -m integration
"""
import pytest
from nuvem_de_som import SoundCloud


ARTIST_URL = "https://soundcloud.com/acidkid"
# acidkid is the URL slug; the real display name returned by the API is "Piratech"
ARTIST_DISPLAY_NAME = "Piratech"
SET_URL = "https://soundcloud.com/acidkid/sets/acid"


def _assert_track(track: dict) -> None:
    for key in ("title", "url", "artist", "artist_url", "image", "duration"):
        assert key in track, f"track missing expected key: {key!r}"
    assert track["url"].startswith("https://soundcloud.com/"), (
        f"unexpected url: {track['url']}"
    )


@pytest.mark.integration
def test_get_tracks_full_returns_tracks():
    tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=50))
    assert len(tracks) > 0, "expected at least one track"
    for t in tracks:
        _assert_track(t)


@pytest.mark.integration
def test_get_tracks_full_more_than_html_scrape():
    """Verify full pagination yields more results than the HTML-scrape path."""
    html_tracks = list(SoundCloud.get_tracks(ARTIST_URL, extract_streams=False))
    full_tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=200))
    assert len(full_tracks) >= len(html_tracks), (
        f"expected full >= html: {len(full_tracks)} vs {len(html_tracks)}"
    )


@pytest.mark.integration
def test_get_tracks_full_real_artist_name():
    """API returns the display name, not the URL slug."""
    tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=5))
    assert tracks, "no tracks returned"
    assert tracks[0]["artist"] == ARTIST_DISPLAY_NAME, (
        f"expected artist {ARTIST_DISPLAY_NAME!r}, got {tracks[0]['artist']!r}"
    )


@pytest.mark.integration
def test_get_tracks_full_has_artwork_and_duration():
    tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=5))
    assert tracks, "no tracks returned"
    # At least some tracks should have artwork and duration
    assert any(t["image"] for t in tracks), "expected at least one track with artwork"
    assert any(t["duration"] for t in tracks), "expected at least one track with duration"


@pytest.mark.integration
def test_get_tracks_full_set_url():
    tracks = list(SoundCloud.get_tracks_full(SET_URL, limit=50))
    assert len(tracks) > 0, "expected at least one track in set"
    for t in tracks:
        _assert_track(t)


@pytest.mark.integration
def test_get_tracks_full_respects_limit():
    limit = 10
    tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=limit))
    assert len(tracks) <= limit, (
        f"expected at most {limit} tracks, got {len(tracks)}"
    )
