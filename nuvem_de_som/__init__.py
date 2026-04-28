import requests
import yt_dlp
from bs4 import BeautifulSoup


class SoundCloud:
    @staticmethod
    def search(query, extract_streams=True):
        """Combined search yielding tracks from people, sets, and direct track search.

        Uses the API v2 methods (full metadata, no per-track follow-up requests)
        with a fallback to the original HTML scrapers if the API is unavailable.
        ``extract_streams`` is honoured only when falling back to the HTML path.
        """
        try:
            sc = SoundCloud._get_sc_extractor()
        except Exception:
            sc = None

        if sc is not None:
            # API path — full metadata, no extra requests
            try:
                for item in SoundCloud.search_people_api(query, limit=3):
                    for t in SoundCloud.get_tracks_full(item["artist_url"], limit=5):
                        yield t
                for item in SoundCloud.search_playlists_api(query, limit=3):
                    for t in SoundCloud.get_tracks_full(item["url"], limit=5):
                        yield t
                for t in SoundCloud.search_tracks_api(query, limit=10):
                    yield t
                return
            except Exception:
                pass  # fall through to HTML scrapers

        # HTML scraper fallback
        for item in SoundCloud.search_people(query, extract_streams):
            for t in item["tracks"]:
                yield t
            break
        for item in SoundCloud.search_sets(query, extract_streams):
            for t in item["tracks"]:
                yield t
            break
        for t in SoundCloud.search_tracks(query, extract_streams):
            yield t

    @staticmethod
    def search_tracks(query, extract_streams=True):
        url = "https://soundcloud.com/search/sounds?q=" + query
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('h2'):
            r = link.find('a')
            url = r.get('href')
            if url.startswith("/"):
                url = "https://soundcloud.com" + url
            info = {
                "title": link.text,
                "url": url
            }
            if extract_streams:
                info = SoundCloud._extract_streams(url)
            yield info

    @staticmethod
    def search_tracks_meta(query):
        """Search tracks and enrich with artist/image via page scrape — no yt-dlp required."""
        for info in SoundCloud.search_tracks(query, extract_streams=False):
            track_url = info.get("url", "")
            try:
                enriched = SoundCloud._scrape_track_meta(track_url)
                info.update(enriched)
            except Exception:
                pass
            yield info

    @staticmethod
    def search_tracks_api(query, limit=10):
        """Search tracks via SoundCloud API v2 — returns full metadata in one call.

        Each yielded dict contains ``title``, ``url``, ``artist``, ``artist_url``,
        ``image``, and ``duration`` (seconds).  No per-track follow-up requests needed.
        """
        try:
            sc = SoundCloud._get_sc_extractor()
            data = sc._call_api(
                "https://api-v2.soundcloud.com/search/tracks", None,
                query={"q": query, "limit": limit},
            )
        except Exception:
            return
        for t in data.get("collection") or []:
            yield SoundCloud._parse_api_track(t)

    @staticmethod
    def search_people_api(query, limit=10):
        """Search users/artists via SoundCloud API v2 — returns full metadata in one call.

        Each yielded dict contains ``artist``, ``artist_url``, and ``image``.
        """
        try:
            sc = SoundCloud._get_sc_extractor()
            data = sc._call_api(
                "https://api-v2.soundcloud.com/search/users", None,
                query={"q": query, "limit": limit},
            )
        except Exception:
            return
        for u in data.get("collection") or []:
            yield {
                "artist": u.get("username") or "",
                "artist_url": u.get("permalink_url") or "",
                "image": u.get("avatar_url") or "",
            }

    @staticmethod
    def resolve_user(profile_url):
        """Resolve a SoundCloud profile URL to a user info dict.

        Returns a dict with ``artist``, ``artist_url``, and ``image``,
        or None if the URL cannot be resolved.
        """
        try:
            sc = SoundCloud._get_sc_extractor()
            u = sc._call_api(
                "https://api-v2.soundcloud.com/resolve", None,
                query={"url": profile_url},
            )
            if u.get("kind") != "user":
                return None
            return {
                "artist": u.get("username") or "",
                "artist_url": u.get("permalink_url") or profile_url,
                "image": u.get("avatar_url") or "",
            }
        except Exception:
            return None

    @staticmethod
    def search_playlists_api(query, limit=10):
        """Search playlists/sets via SoundCloud API v2 — returns full metadata in one call.

        Each yielded dict contains ``title``, ``url``, ``artist``, ``artist_url``, and ``image``.
        """
        try:
            sc = SoundCloud._get_sc_extractor()
            data = sc._call_api(
                "https://api-v2.soundcloud.com/search/playlists", None,
                query={"q": query, "limit": limit},
            )
        except Exception:
            return
        for p in data.get("collection") or []:
            user = p.get("user") or {}
            image = p.get("artwork_url") or user.get("avatar_url") or ""
            yield {
                "title": p.get("title") or "",
                "url": p.get("permalink_url") or "",
                "artist": user.get("username") or "",
                "artist_url": user.get("permalink_url") or "",
                "image": image,
            }

    @staticmethod
    def _scrape_track_meta(track_url):
        """Extract artist name and thumbnail from a SoundCloud track page without yt-dlp."""
        import json as _json  # noqa: PLC0415
        resp = requests.get(track_url, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")

        # og:image for artwork
        image = None
        og_img = soup.find("meta", property="og:image")
        if og_img:
            image = og_img.get("content")

        # og:description or structured data for artist
        artist = None
        ld = soup.find("script", type="application/ld+json")
        if ld:
            try:
                data = _json.loads(ld.string or "{}")
                artist = (data.get("author") or {}).get("name")
            except Exception:
                pass
        if not artist:
            username_tag = soup.find("a", attrs={"itemprop": "url"})
            if username_tag:
                artist = username_tag.text.strip()

        return {k: v for k, v in {"artist": artist, "image": image}.items() if v}

    @staticmethod
    def search_people(query, extract_streams=True):
        url = "https://soundcloud.com/search/people?q=" + query
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('h2'):
            r = link.find('a')
            url = r.get('href')
            if url.startswith("/"):
                url = "https://soundcloud.com" + url
            artist = link.text
            info = {
                "artist": artist,
                "url": url,
                "tracks": []
            }
            info["tracks"] = list(SoundCloud.get_tracks(url,
                                                        extract_streams=extract_streams))
            yield info

    @staticmethod
    def search_sets(query, extract_streams=True):
        url = "https://soundcloud.com/search/sets?q=" + query
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('h2'):
            r = link.find('a')
            url = r.get('href')
            if url.startswith("/"):
                url = "https://soundcloud.com" + url
            title = link.text
            info = {
                "title": title,
                "url": url
            }
            info["tracks"] = list(SoundCloud.get_tracks(url,
                                                        extract_streams=extract_streams))

            yield info

    @staticmethod
    def get_tracks(url, extract_streams=False):
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        for item in soup.find_all("article"):
            try:
                link = item.find("h2")
                title = link.text.strip()
                r = item.find('a')
                track_url = r.get('href')
                if track_url.startswith("/"):
                    track_url = "https://soundcloud.com" + track_url
                if track_url == url:
                    continue
                info = {"title": title,
                        "url": track_url}
                if extract_streams:
                    info = SoundCloud._extract_streams(track_url)
                yield info
            except:  # debug
                continue

    @staticmethod
    def _get_sc_extractor():
        """Return an initialized yt-dlp SoundCloud extractor with a valid client_id."""
        ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True})
        sc = ydl.get_info_extractor("Soundcloud")
        sc.set_downloader(ydl)
        sc._update_client_id()
        return sc

    @staticmethod
    def _parse_api_track(t, artist_url=None):
        """Convert a SoundCloud API v2 track dict to the nuvem_de_som track format."""
        user = t.get("user") or {}
        # artwork_url falls back to the user's avatar when the track has no cover
        image = t.get("artwork_url") or user.get("avatar_url") or ""
        # API returns duration in milliseconds
        duration = (t["duration"] // 1000) if t.get("duration") else None
        return {
            "title": t.get("title") or "",
            "url": t.get("permalink_url") or "",
            "artist": user.get("username") or "",
            "artist_url": artist_url or user.get("permalink_url") or "",
            "image": image,
            "duration": duration,
        }

    @staticmethod
    def get_tracks_full(url, limit=200):
        """Return all tracks for a profile or set URL with full metadata.

        Uses SoundCloud's API v2 (client_id auto-managed by yt-dlp, refreshed
        on 401/403) to paginate through the complete catalogue. Each yielded
        dict always contains: ``title``, ``url``, ``artist``, ``artist_url``,
        ``image``, ``duration``.

        Unlike get_tracks(), which scrapes HTML and is capped at ~20 items,
        this method returns the real artist display name (e.g. "Piratech"
        rather than the URL slug "acidkid"), per-track artwork, and duration
        for every track.
        """
        try:
            sc = SoundCloud._get_sc_extractor()
            resource = sc._call_api(
                "https://api-v2.soundcloud.com/resolve", None,
                query={"url": url},
            )
        except Exception:
            return

        kind = resource.get("kind")
        collected = 0

        if kind == "user":
            user_id = resource["id"]
            artist_url = resource.get("permalink_url") or url
            next_href = f"https://api-v2.soundcloud.com/users/{user_id}/tracks"
            while next_href and collected < limit:
                try:
                    data = sc._call_api(next_href, None,
                                        query={"limit": 50, "linked_partitioning": 1})
                except Exception:
                    break
                for t in data.get("collection") or []:
                    if collected >= limit:
                        break
                    yield SoundCloud._parse_api_track(t, artist_url=artist_url)
                    collected += 1
                next_href = data.get("next_href")

        elif kind == "playlist":
            artist_url = (resource.get("user") or {}).get("permalink_url") or ""
            for t in resource.get("tracks") or []:
                if collected >= limit:
                    break
                # Playlist tracks may be stubs (only id/kind) — skip those
                if not t.get("title"):
                    continue
                yield SoundCloud._parse_api_track(t, artist_url=artist_url)
                collected += 1

    @staticmethod
    def _extract_streams(track_url, prefered_ext=None, verbose=False):
        ydl_opts = {"quiet": not verbose, "verbose": verbose}
        kmaps = {"duration": "duration",
                 "thumbnail": "image",
                 "uploader": "artist",
                 "title": "title",
                 'webpage_url': "url"}
        info = {}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(track_url, download=False)
            for k, v in kmaps.items():
                info[v] = meta.get(k)
            formats = meta.get("formats") or []
            if formats:
                info["uri"] = formats[-1]["url"]
                if prefered_ext:
                    for f in formats:
                        if f.get("ext") == prefered_ext:
                            info["uri"] = f["url"]
                            break
            else:
                info["uri"] = meta.get("url")
        return info

