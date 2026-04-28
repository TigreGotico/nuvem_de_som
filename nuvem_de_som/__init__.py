"""nuvem_de_som — SoundCloud search, stream, and download client.

Three independent concrete backends, one orchestrator:

- ``SoundCloudAPI``    — SoundCloud internal API v2.  Full metadata in one call.
                         Requires only ``requests``.  Recommended.
- ``SoundCloudHTML``   — HTML page scraper.  No API key, ~20 results per page.
                         No extra deps.
- ``SoundCloudYTDLP``  — yt-dlp backed.  Best stream resolution; slower search.
                         Requires ``pip install nuvem_de_som[streams]``.
                         Download methods (``download_track``, ``download_tracks``,
                         ``download_playlist``) are only available on this backend
                         and on the ``SoundCloud`` orchestrator.
- ``SoundCloud``       — Orchestrator.  Tries API → yt-dlp → HTML, falls back
                         transparently on errors.  Download methods delegate to
                         the yt-dlp backend.  Use concrete classes directly when
                         you need a specific backend.

Quick start::

    from nuvem_de_som import SoundCloud, SoundCloudAPI, SoundCloudHTML, SoundCloudYTDLP

    sc = SoundCloud()        # orchestrator: API → yt-dlp → HTML
    sc = SoundCloudAPI()     # API only (recommended)
    sc = SoundCloudHTML()    # HTML scraper only
    sc = SoundCloudYTDLP()   # yt-dlp only

    for t in sc.search_tracks("nuclear chill", limit=5):
        print(t["title"], t["artist"])

    # Downloads require yt-dlp (pip install nuvem_de_som[streams])
    # Only available on SoundCloudYTDLP and SoundCloud (orchestrator)
    sc = SoundCloud()  # or SoundCloudYTDLP()
    sc.download_track("https://soundcloud.com/user/track", output_dir="~/Music")
    sc.download_playlist("https://soundcloud.com/user", output_dir="~/Music")

All track dicts share the same schema regardless of backend::

    {
        "title": str,
        "url": str,            # SoundCloud permalink
        "artist": str,         # display name ("" when not available)
        "artist_url": str,     # profile URL ("" when not available)
        "image": str,          # artwork URL ("" when not available)
        "duration": int|None,  # seconds, None when not available
    }
"""

from __future__ import annotations

import logging
import re
import threading
import urllib.parse
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_PREFER_VALUES = frozenset(("progressive", "hls"))

# ---------------------------------------------------------------------------
# client_id management — pure requests, no yt-dlp
# ---------------------------------------------------------------------------

_CLIENT_ID: str | None = None
_CLIENT_ID_LOCK = threading.Lock()

_CLIENT_ID_PATTERNS = [
    r'"client_id"\s*:\s*"([0-9a-zA-Z]{32})"',
    r"client_id\s*:\s*\"([0-9a-zA-Z]{32})\"",
    r"client_id=([0-9a-zA-Z]{32})",
]

_SC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
    )
}


def _fetch_client_id() -> str:
    """Extract SoundCloud API client_id from their bundled JS files."""
    resp = requests.get("https://soundcloud.com/", timeout=10, headers=_SC_HEADERS)
    resp.raise_for_status()
    script_urls = re.findall(r'<script[^>]+src="(https://[^"]+\.js[^"]*)"', resp.text)
    for src in reversed(script_urls):  # last bundles contain app config
        try:
            js = requests.get(src, timeout=10).text
            for pat in _CLIENT_ID_PATTERNS:
                m = re.search(pat, js)
                if m:
                    return m.group(1)
        except requests.RequestException as exc:
            log.debug("Failed to fetch JS bundle %s: %s", src, exc)
            continue
    raise RuntimeError("Could not extract SoundCloud client_id from JS bundles")


def _get_client_id() -> str:
    global _CLIENT_ID
    with _CLIENT_ID_LOCK:
        if not _CLIENT_ID:
            _CLIENT_ID = _fetch_client_id()
        return _CLIENT_ID


def _invalidate_client_id() -> None:
    global _CLIENT_ID
    with _CLIENT_ID_LOCK:
        _CLIENT_ID = None


def _ydl_import():
    try:
        import yt_dlp  # noqa: PLC0415
        return yt_dlp
    except ImportError as e:
        raise ImportError(
            "yt-dlp is required for downloads; "
            "install with: pip install nuvem_de_som[streams]"
        ) from e


def _empty_track(url: str = "") -> dict:
    """Return an empty track dict with the canonical key set."""
    return {"title": "", "url": url, "artist": "", "artist_url": "", "image": "",
            "duration": None}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class SoundCloudBase(ABC):
    """Abstract interface — one class per backend, all methods required.

    Every track dict yielded by any subclass has exactly these keys::

        title, url, artist, artist_url, image, duration

    Missing values are empty string (str keys) or None (duration).
    """

    # -- required ------------------------------------------------------------

    @abstractmethod
    def search_tracks(self, query: str, limit: int = 10) -> Iterator[dict]:
        """Yield track dicts matching *query*."""

    @abstractmethod
    def search_people(self, query: str, limit: int = 10) -> Iterator[dict]:
        """Yield artist/user dicts matching *query*.

        Each dict has: ``artist``, ``artist_url``, ``image``.
        """

    @abstractmethod
    def search_sets(self, query: str, limit: int = 10) -> Iterator[dict]:
        """Yield playlist/set dicts matching *query*.

        Each dict has: ``title``, ``url``, ``artist``, ``artist_url``, ``image``.
        """

    @abstractmethod
    def get_tracks(self, url: str, limit: int = 200) -> Iterator[dict]:
        """Yield track dicts for an artist profile or set URL."""

    @abstractmethod
    def resolve_stream(self, track_url: str, prefer: str = "progressive") -> str | None:
        """Resolve a SoundCloud track URL to a direct audio stream URL.

        Parameters
        ----------
        track_url:
            SoundCloud track permalink.
        prefer:
            ``"progressive"`` (direct MP3/AAC, seekable) or ``"hls"`` (m3u8).

        Returns the stream URL string, or ``None`` when not resolvable.
        """

    @abstractmethod
    def resolve_user(self, profile_url: str) -> dict | None:
        """Resolve a profile URL to ``{"artist", "artist_url", "image"}`` or None."""

    # -- concrete shared -----------------------------------------------------

    def search(self, query: str, limit: int = 10) -> Iterator[dict]:
        """Combined search: artist tracks + set tracks + direct track search."""
        for person in self.search_people(query, limit=3):
            url = person.get("artist_url") or person.get("url") or ""
            if url:
                yield from self.get_tracks(url, limit=5)
        for pl in self.search_sets(query, limit=3):
            url = pl.get("url") or ""
            if url:
                yield from self.get_tracks(url, limit=5)
        yield from self.search_tracks(query, limit=limit)


# ---------------------------------------------------------------------------
# Backend 1: SoundCloud API v2
# ---------------------------------------------------------------------------

class SoundCloudAPI(SoundCloudBase):
    """SoundCloud internal API v2 backend.

    Full metadata (display name, artwork, duration) in a single call per query.
    Requires only ``requests`` — no yt-dlp for search, listing, or stream
    resolution.  Stream resolution uses the transcodings endpoint natively.
    """

    def _call(self, endpoint: str, **params) -> dict:
        """Call an API v2 endpoint; refresh client_id automatically on 401/403."""
        for attempt in range(2):
            cid = _get_client_id()
            resp = requests.get(
                endpoint,
                params={"client_id": cid, **params},
                timeout=10,
                headers=_SC_HEADERS,
            )
            if resp.status_code in (401, 403) and attempt == 0:
                log.debug("client_id rejected (%s), refreshing", resp.status_code)
                _invalidate_client_id()
                continue
            resp.raise_for_status()
            return resp.json()
        # unreachable: the loop always returns or raises above
        raise RuntimeError("unexpected exit from _call retry loop")

    @staticmethod
    def _parse_track(t: dict, artist_url: str | None = None) -> dict:
        user = t.get("user") or {}
        image = t.get("artwork_url") or user.get("avatar_url") or ""
        duration = (t["duration"] // 1000) if t.get("duration") else None
        return {
            "title": t.get("title") or "",
            "url": t.get("permalink_url") or "",
            "artist": user.get("username") or "",
            "artist_url": artist_url or user.get("permalink_url") or "",
            "image": image,
            "duration": duration,
        }

    def search_tracks(self, query: str, limit: int = 10) -> Iterator[dict]:
        data = self._call(
            "https://api-v2.soundcloud.com/search/tracks", q=query, limit=limit
        )
        for t in data.get("collection") or []:
            yield self._parse_track(t)

    def search_people(self, query: str, limit: int = 10) -> Iterator[dict]:
        data = self._call(
            "https://api-v2.soundcloud.com/search/users", q=query, limit=limit
        )
        for u in data.get("collection") or []:
            yield {
                "artist": u.get("username") or "",
                "artist_url": u.get("permalink_url") or "",
                "image": u.get("avatar_url") or "",
            }

    def search_sets(self, query: str, limit: int = 10) -> Iterator[dict]:
        data = self._call(
            "https://api-v2.soundcloud.com/search/playlists", q=query, limit=limit
        )
        for p in data.get("collection") or []:
            user = p.get("user") or {}
            yield {
                "title": p.get("title") or "",
                "url": p.get("permalink_url") or "",
                "artist": user.get("username") or "",
                "artist_url": user.get("permalink_url") or "",
                "image": p.get("artwork_url") or user.get("avatar_url") or "",
            }

    def get_tracks(self, url: str, limit: int = 200) -> Iterator[dict]:
        resource = self._call("https://api-v2.soundcloud.com/resolve", url=url)
        kind = resource.get("kind")
        collected = 0

        if kind == "user":
            user_id = resource["id"]
            artist_url = resource.get("permalink_url") or url
            next_href = f"https://api-v2.soundcloud.com/users/{user_id}/tracks"
            while next_href and collected < limit:
                page_size = min(50, limit - collected)
                page = self._call(next_href, limit=page_size, linked_partitioning=1)
                for t in page.get("collection") or []:
                    if collected >= limit:
                        return
                    yield self._parse_track(t, artist_url=artist_url)
                    collected += 1
                next_href = page.get("next_href")

        elif kind == "playlist":
            artist_url = (resource.get("user") or {}).get("permalink_url") or ""
            for t in resource.get("tracks") or []:
                if collected >= limit:
                    return
                if not t.get("title"):
                    log.debug("get_tracks: skipping untitled track in playlist %s", url)
                    continue
                yield self._parse_track(t, artist_url=artist_url)
                collected += 1

        else:
            log.debug("get_tracks: unexpected resource kind %r for %s", kind, url)

    def resolve_stream(self, track_url: str, prefer: str = "progressive") -> str | None:
        """Resolve track URL to a direct audio stream via transcodings — no yt-dlp.

        Parameters
        ----------
        prefer:
            ``"progressive"`` (direct MP3/AAC, seekable) or ``"hls"`` (m3u8).
        """
        if prefer not in _PREFER_VALUES:
            raise ValueError(f"prefer must be 'progressive' or 'hls'; got {prefer!r}")
        try:
            resource = self._call("https://api-v2.soundcloud.com/resolve", url=track_url)
            transcodings = resource.get("media", {}).get("transcodings") or []
            ordered = sorted(
                transcodings,
                key=lambda t: 0 if t.get("format", {}).get("protocol") == prefer else 1,
            )
            for tc in ordered:
                stream_url = tc.get("url")
                if not stream_url:
                    continue
                data = self._call(stream_url)
                result = data.get("url")
                if result:
                    return result
        except Exception as exc:
            log.debug("resolve_stream failed for %s: %s", track_url, exc)
        return None

    def resolve_user(self, profile_url: str) -> dict | None:
        """Resolve a profile URL to display name + avatar via API v2."""
        try:
            u = self._call("https://api-v2.soundcloud.com/resolve", url=profile_url)
            if u.get("kind") != "user":
                return None
            return {
                "artist": u.get("username") or "",
                "artist_url": u.get("permalink_url") or profile_url,
                "image": u.get("avatar_url") or "",
            }
        except Exception as exc:
            log.debug("resolve_user failed for %s: %s", profile_url, exc)
            return None


# ---------------------------------------------------------------------------
# Backend 2: HTML scraper
# ---------------------------------------------------------------------------

class SoundCloudHTML(SoundCloudBase):
    """HTML page scraping backend.

    No API key or yt-dlp needed for metadata.  Artist/set pages return full
    track metadata (artist, artist_url, duration) via schema.org markup.
    Search result pages return title + URL only (no artwork or duration in
    SoundCloud's search HTML).

    ``resolve_stream()`` delegates to yt-dlp when installed; returns ``None``
    otherwise.  ``resolve_user()`` scrapes Open Graph / JSON-LD from the profile
    page — no API required.

    All track dicts always include the canonical key set; missing values are
    empty string or ``None`` for duration.
    """

    @staticmethod
    def _get_soup(url: str) -> BeautifulSoup:
        resp = requests.get(url, timeout=10, headers=_SC_HEADERS)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")

    @staticmethod
    def _abs(href: str) -> str:
        return href if href.startswith("http") else "https://soundcloud.com" + href

    @staticmethod
    def _parse_duration(iso: str | None) -> int | None:
        """Parse ISO 8601 duration ``PT00H03M09S`` → seconds, or None on failure."""
        if not iso:
            return None
        m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
        # Require at least one component to be present; reject bare "PT"
        if not m or not any(m.groups()):
            return None
        h, mins, s = (int(x or 0) for x in m.groups())
        return h * 3600 + mins * 60 + s

    def search_tracks(self, query: str, limit: int = 10) -> Iterator[dict]:
        soup = self._get_soup(
            "https://soundcloud.com/search/sounds?q=" + urllib.parse.quote(query)
        )
        for i, h2 in enumerate(soup.find_all("h2")):
            if i >= limit:
                break
            a = h2.find("a")
            if not a:
                continue
            yield {
                "title": a.get_text(strip=True),
                "url": self._abs(a.get("href", "")),
                "artist": "",
                "artist_url": "",
                "image": "",
                "duration": None,
            }

    def search_people(self, query: str, limit: int = 10) -> Iterator[dict]:
        soup = self._get_soup(
            "https://soundcloud.com/search/people?q=" + urllib.parse.quote(query)
        )
        for i, h2 in enumerate(soup.find_all("h2")):
            if i >= limit:
                break
            a = h2.find("a")
            if not a:
                continue
            href = self._abs(a.get("href", ""))
            yield {
                "artist": a.get_text(strip=True),
                "artist_url": href,
                "image": "",
            }

    def search_sets(self, query: str, limit: int = 10) -> Iterator[dict]:
        soup = self._get_soup(
            "https://soundcloud.com/search/sets?q=" + urllib.parse.quote(query)
        )
        for i, h2 in enumerate(soup.find_all("h2")):
            if i >= limit:
                break
            a = h2.find("a")
            if not a:
                continue
            href = self._abs(a.get("href", ""))
            yield {
                "title": a.get_text(strip=True),
                "url": href,
                "artist": "",
                "artist_url": "",
                "image": "",
            }

    def get_tracks(self, url: str, limit: int = 20) -> Iterator[dict]:
        """Scrape tracks from an artist or set page.

        Extracts title, URL, artist, artist_url, and duration from the
        schema.org MusicRecording markup — no extra requests, no yt-dlp.
        Images are not available via HTML scraping (empty string).
        """
        soup = self._get_soup(url)
        collected = 0
        for item in soup.find_all("article", itemprop="track"):
            if collected >= limit:
                break
            try:
                h2 = item.find("h2", itemprop="name")
                if not h2:
                    continue
                links = h2.find_all("a")
                if not links:
                    continue
                track_a = links[0]
                track_href = self._abs(track_a.get("href", ""))
                if track_href == url:
                    continue
                title = track_a.get_text(strip=True)
                artist_name, artist_href = "", ""
                if len(links) >= 2:
                    artist_a = links[1]
                    artist_name = artist_a.get_text(strip=True)
                    artist_href = self._abs(artist_a.get("href", ""))
                dur_meta = item.find("meta", itemprop="duration")
                duration = self._parse_duration(
                    dur_meta.get("content") if dur_meta else None
                )
                yield {
                    "title": title,
                    "url": track_href,
                    "artist": artist_name,
                    "artist_url": artist_href,
                    "image": "",
                    "duration": duration,
                }
                collected += 1
            except Exception as exc:
                log.debug("HTML get_tracks parse error: %s", exc)
                continue

    def resolve_stream(self, track_url: str, prefer: str = "progressive") -> str | None:
        """Not supported by the HTML backend.

        SoundCloud stream URLs are signed and not available in page HTML.
        Use ``SoundCloudAPI`` or ``SoundCloudYTDLP`` for stream resolution.
        """
        raise NotImplementedError(
            "SoundCloudHTML cannot resolve stream URLs. "
            "Use SoundCloudAPI (no extra deps) or SoundCloudYTDLP."
        )

    def resolve_user(self, profile_url: str) -> dict | None:
        """Scrape display name and avatar from a profile page via Open Graph / JSON-LD."""
        import json as _json  # noqa: PLC0415
        try:
            soup = self._get_soup(profile_url)
            artist: str | None = None
            image: str | None = None

            og_title = soup.find("meta", property="og:title")
            if og_title:
                artist = og_title.get("content", "").split(" |")[0].strip() or None
            og_img = soup.find("meta", property="og:image")
            if og_img:
                image = og_img.get("content")

            if not artist:
                ld = soup.find("script", type="application/ld+json")
                if ld:
                    try:
                        artist = _json.loads(ld.string or "{}").get("name") or None
                    except Exception:
                        pass

            if not artist:
                return None
            return {"artist": artist, "artist_url": profile_url, "image": image or ""}
        except Exception as exc:
            log.debug("HTML resolve_user failed for %s: %s", profile_url, exc)
            return None

    # -- HTML-specific helpers -----------------------------------------------

    def get_track_meta(self, track_url: str) -> dict:
        """Scrape artist name and thumbnail from a track page (no yt-dlp).

        Makes one extra HTTP request.  Use ``get_tracks()`` on an artist page
        for bulk metadata without extra requests.
        """
        import json as _json  # noqa: PLC0415
        soup = self._get_soup(track_url)
        image, artist = None, None
        og_img = soup.find("meta", property="og:image")
        if og_img:
            image = og_img.get("content")
        ld = soup.find("script", type="application/ld+json")
        if ld:
            try:
                artist = (_json.loads(ld.string or "{}").get("author") or {}).get("name")
            except Exception:
                pass
        if not artist:
            tag = soup.find("a", attrs={"itemprop": "url"})
            if tag:
                artist = tag.get_text(strip=True)
        return {k: v for k, v in {"artist": artist, "image": image}.items() if v}

    def search_tracks_enriched(self, query: str, limit: int = 10) -> Iterator[dict]:
        """search_tracks with artist + image added (one extra HTTP request per track).

        Prefer ``SoundCloudAPI.search_tracks()`` when full metadata is needed
        without extra requests.
        """
        for info in self.search_tracks(query, limit=limit):
            try:
                info.update(self.get_track_meta(info["url"]))
            except Exception as exc:
                log.debug("Enrichment failed for %s: %s", info.get("url"), exc)
            yield info


# Keep old name as alias for backwards compatibility
SoundCloudScraper = SoundCloudHTML


# ---------------------------------------------------------------------------
# Backend 3: yt-dlp
# ---------------------------------------------------------------------------

class SoundCloudYTDLP(SoundCloudBase):
    """yt-dlp backed SoundCloud client.

    All operations go through yt-dlp.  Provides the most resilient stream
    resolution (yt-dlp tends to be patched faster when SoundCloud rotates
    their signing scheme), but is slower and has no people/set search.

    ``search_people()`` and ``search_sets()`` yield nothing — yt-dlp does not
    expose those endpoints.

    Requires ``pip install nuvem_de_som[streams]``.
    """

    @staticmethod
    def _ydl(extra_opts: dict | None = None):
        yt_dlp = _ydl_import()
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }
        opts.update(extra_opts or {})
        return yt_dlp.YoutubeDL(opts)

    @staticmethod
    def _entry_to_track(entry: dict, artist_url: str = "") -> dict:
        return {
            "title": entry.get("title") or "",
            "url": entry.get("url") or entry.get("webpage_url") or "",
            "artist": entry.get("uploader") or entry.get("channel") or "",
            "artist_url": artist_url,
            "image": entry.get("thumbnail") or "",
            "duration": entry.get("duration"),
        }

    def search_tracks(self, query: str, limit: int = 10) -> Iterator[dict]:
        with self._ydl() as ydl:
            info = ydl.extract_info(f"scsearch{limit}:{query}", download=False) or {}
        for entry in info.get("entries") or []:
            yield self._entry_to_track(entry)

    def search_people(self, query: str, limit: int = 10) -> Iterator[dict]:
        # yt-dlp has no people search endpoint
        return iter([])

    def search_sets(self, query: str, limit: int = 10) -> Iterator[dict]:
        # yt-dlp has no set search endpoint
        return iter([])

    def get_tracks(self, url: str, limit: int = 200) -> Iterator[dict]:
        with self._ydl({"playlistend": limit}) as ydl:
            info = ydl.extract_info(url, download=False) or {}
        artist_url = url if "/sets/" not in url else ""
        for entry in info.get("entries") or []:
            yield self._entry_to_track(entry, artist_url=artist_url)

    def resolve_stream(self, track_url: str, prefer: str = "progressive") -> str | None:
        """Resolve stream URL via yt-dlp full extraction."""
        if prefer not in _PREFER_VALUES:
            raise ValueError(f"prefer must be 'progressive' or 'hls'; got {prefer!r}")
        try:
            yt_dlp = _ydl_import()
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(track_url, download=False) or {}
                formats = info.get("formats") or []
                target_protocol = "https" if prefer == "progressive" else "m3u8_native"
                for f in reversed(formats):
                    if f.get("protocol") == target_protocol:
                        return f["url"]
                # fall back to any format if preferred protocol not found
                return formats[-1]["url"] if formats else info.get("url")
        except ImportError:
            raise
        except Exception as exc:
            log.debug("yt-dlp resolve_stream failed for %s: %s", track_url, exc)
            return None

    def resolve_user(self, profile_url: str) -> dict | None:
        """Resolve user metadata via yt-dlp channel extraction."""
        try:
            yt_dlp = _ydl_import()
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                                   "extract_flat": True, "playlistend": 0}) as ydl:
                info = ydl.extract_info(profile_url, download=False) or {}
            uploader = info.get("uploader") or info.get("channel") or ""
            if not uploader:
                return None
            return {
                "artist": uploader,
                "artist_url": profile_url,
                "image": info.get("thumbnail") or "",
            }
        except ImportError:
            raise
        except Exception as exc:
            log.debug("yt-dlp resolve_user failed for %s: %s", profile_url, exc)
            return None

    # -- download ------------------------------------------------------------

    def _download_urls(self, urls: list[str], output_dir: str, audio_format: str,
                       verbose: bool, outtmpl_suffix: str) -> list[Path]:
        yt_dlp = _ydl_import()
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        outtmpl = str(out / outtmpl_suffix)
        downloaded: list[Path] = []

        class _Hook:
            def __call__(self, d):
                if d["status"] == "finished":
                    downloaded.append(Path(d["filename"]))

        opts = {
            "quiet": not verbose,
            "outtmpl": outtmpl,
            "progress_hooks": [_Hook()],
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": audio_format}],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download(urls)
        return downloaded

    def download_track(self, track_url: str, output_dir: str = ".",
                       audio_format: str = "mp3", verbose: bool = False) -> Path | None:
        """Download a single track via yt-dlp.

        Parameters
        ----------
        track_url:
            SoundCloud track permalink.
        output_dir:
            Destination directory.
        audio_format:
            Codec for ``--audio-format`` (e.g. ``"mp3"``, ``"aac"``).
        verbose:
            Show yt-dlp output.

        Returns the path of the downloaded file, or ``None`` on failure.
        """
        files = self._download_urls(
            [track_url], output_dir, audio_format, verbose,
            outtmpl_suffix="%(uploader)s - %(title)s.%(ext)s",
        )
        return files[0] if files else None

    def download_tracks(self, track_urls, output_dir: str = ".",
                        audio_format: str = "mp3",
                        verbose: bool = False) -> list[Path]:
        """Download multiple tracks.

        *track_urls* may be any iterable of SoundCloud permalink strings.
        Returns a list of successfully downloaded file paths (failed downloads
        are omitted rather than returning a placeholder path).
        """
        results = []
        for u in track_urls:
            path = self.download_track(u, output_dir=output_dir,
                                       audio_format=audio_format, verbose=verbose)
            if path is not None:
                results.append(path)
        return results

    def download_playlist(self, playlist_url: str, output_dir: str = ".",
                          audio_format: str = "mp3",
                          verbose: bool = False) -> list[Path]:
        """Download every track in an artist page or set URL via yt-dlp.

        A sub-folder named after the artist is created automatically inside
        *output_dir*.
        """
        return self._download_urls(
            [playlist_url], output_dir, audio_format, verbose,
            outtmpl_suffix="%(uploader)s/%(title)s.%(ext)s",
        )


# ---------------------------------------------------------------------------
# Orchestrator — subclass of SoundCloudBase, falls through to concrete backends
# ---------------------------------------------------------------------------

class SoundCloud(SoundCloudBase):
    """SoundCloud orchestrator — API v2 → yt-dlp → HTML, with transparent fallback.

    Use the concrete classes directly when you need a specific backend:

    - ``SoundCloudAPI()``    — full metadata, no yt-dlp
    - ``SoundCloudHTML()``   — HTML scraper, no extra deps
    - ``SoundCloudYTDLP()``  — yt-dlp backed stream resolution
    """

    def __init__(self):
        self._chain: list[SoundCloudBase] = [
            SoundCloudAPI(),
            SoundCloudYTDLP(),
            SoundCloudHTML(),
        ]

    def _try_each(self, method: str, *args, **kwargs) -> Iterator[dict]:
        """Yield from the first backend that returns results without raising."""
        for b in self._chain:
            try:
                results = list(getattr(b, method)(*args, **kwargs))
                if results:
                    yield from results
                    return
            except Exception as exc:
                log.debug("%s.%s failed, trying next backend: %s",
                          type(b).__name__, method, exc)
                continue

    def _try_each_value(self, method: str, *args, **kwargs):
        """Return the first non-None result across backends."""
        for b in self._chain:
            try:
                result = getattr(b, method)(*args, **kwargs)
                if result is not None:
                    return result
            except Exception as exc:
                log.debug("%s.%s failed, trying next backend: %s",
                          type(b).__name__, method, exc)
                continue
        return None

    def search_tracks(self, query: str, limit: int = 10) -> Iterator[dict]:
        yield from self._try_each("search_tracks", query, limit=limit)

    def search_people(self, query: str, limit: int = 10) -> Iterator[dict]:
        yield from self._try_each("search_people", query, limit=limit)

    def search_sets(self, query: str, limit: int = 10) -> Iterator[dict]:
        yield from self._try_each("search_sets", query, limit=limit)

    def get_tracks(self, url: str, limit: int = 200) -> Iterator[dict]:
        yield from self._try_each("get_tracks", url, limit=limit)

    def resolve_stream(self, track_url: str, prefer: str = "progressive") -> str | None:
        if prefer not in _PREFER_VALUES:
            raise ValueError(f"prefer must be 'progressive' or 'hls'; got {prefer!r}")
        return self._try_each_value("resolve_stream", track_url, prefer=prefer)

    def resolve_user(self, profile_url: str) -> dict | None:
        return self._try_each_value("resolve_user", profile_url)

    # -- downloads (delegated to yt-dlp backend) -----------------------------

    @property
    def _ytdlp(self) -> SoundCloudYTDLP:
        for b in self._chain:
            if isinstance(b, SoundCloudYTDLP):
                return b
        raise RuntimeError("SoundCloudYTDLP backend not found in chain")

    def download_track(self, track_url: str, output_dir: str = ".",
                       audio_format: str = "mp3", verbose: bool = False) -> Path | None:
        """Download a single track via yt-dlp.

        Delegates to the ``SoundCloudYTDLP`` backend.
        Requires ``pip install nuvem_de_som[streams]``.
        """
        return self._ytdlp.download_track(track_url, output_dir=output_dir,
                                          audio_format=audio_format, verbose=verbose)

    def download_tracks(self, track_urls, output_dir: str = ".",
                        audio_format: str = "mp3",
                        verbose: bool = False) -> list[Path]:
        """Download multiple tracks via yt-dlp.

        Delegates to the ``SoundCloudYTDLP`` backend.
        Returns only paths of successfully downloaded files.
        """
        return self._ytdlp.download_tracks(track_urls, output_dir=output_dir,
                                           audio_format=audio_format, verbose=verbose)

    def download_playlist(self, playlist_url: str, output_dir: str = ".",
                          audio_format: str = "mp3",
                          verbose: bool = False) -> list[Path]:
        """Download every track in an artist page or set URL via yt-dlp.

        Delegates to the ``SoundCloudYTDLP`` backend.
        A sub-folder named after the artist is created automatically inside
        *output_dir*.
        """
        return self._ytdlp.download_playlist(playlist_url, output_dir=output_dir,
                                             audio_format=audio_format, verbose=verbose)
