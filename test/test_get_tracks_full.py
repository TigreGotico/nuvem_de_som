"""Tests for SoundCloud.get_tracks_full().

get_tracks_full() uses yt-dlp's flat extraction to paginate through an artist
or set page via SoundCloud's internal API.  Unlike get_tracks() — which scrapes
HTML and is capped at ~20 items — this method retrieves the complete catalogue.

These tests are integration tests: they hit the real SoundCloud API, so they
require a live network connection and may be slow.  Run selectively with::

    pytest test/test_get_tracks_full.py -v
"""
import pytest
from nuvem_de_som import SoundCloud


ARTIST_URL = "https://soundcloud.com/acidkid"
SET_URL = "https://soundcloud.com/acidkid/sets/acid"


def _required_keys(track: dict) -> None:
    assert "title" in track, "track missing 'title'"
    assert "url" in track, "track missing 'url'"
    assert track["url"].startswith("https://soundcloud.com/"), (
        f"unexpected url: {track['url']}"
    )


@pytest.mark.integration
def test_get_tracks_full_returns_tracks():
    tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=50))
    assert len(tracks) > 0, "expected at least one track"
    for t in tracks:
        _required_keys(t)


@pytest.mark.integration
def test_get_tracks_full_more_than_html_scrape():
    """Verify full pagination yields more results than the HTML-scrape path."""
    html_tracks = list(SoundCloud.get_tracks(ARTIST_URL, extract_streams=False))
    full_tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=200))
    assert len(full_tracks) >= len(html_tracks), (
        f"expected full >= html: {len(full_tracks)} vs {len(html_tracks)}"
    )


@pytest.mark.integration
def test_get_tracks_full_set_url():
    tracks = list(SoundCloud.get_tracks_full(SET_URL, limit=50))
    assert len(tracks) > 0, "expected at least one track in set"
    for t in tracks:
        _required_keys(t)


@pytest.mark.integration
def test_get_tracks_full_track_fields():
    tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=5))
    assert tracks, "no tracks returned"
    t = tracks[0]
    # These fields come from yt-dlp flat extraction; they may be empty strings
    # but the keys must be present so callers can rely on them
    for key in ("title", "url", "artist", "image", "duration"):
        assert key in t, f"track missing expected key: {key!r}"


@pytest.mark.integration
def test_get_tracks_full_respects_limit():
    limit = 10
    tracks = list(SoundCloud.get_tracks_full(ARTIST_URL, limit=limit))
    assert len(tracks) <= limit, (
        f"expected at most {limit} tracks, got {len(tracks)}"
    )
