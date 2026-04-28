import requests
import yt_dlp
from bs4 import BeautifulSoup


class SoundCloud:
    @staticmethod
    def search(query, extract_streams=True):
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
    def get_tracks_full(url, limit=200):
        """Return all tracks for a profile or set URL using yt-dlp flat extraction.

        Unlike get_tracks(), this uses SoundCloud's API via yt-dlp and paginates
        through the full catalogue rather than being limited to the first HTML page.
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "playlistend": limit,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
        for entry in info.get("entries") or []:
            track_url = entry.get("url") or entry.get("webpage_url") or ""
            if not track_url:
                continue
            yield {
                "title": entry.get("title") or track_url,
                "url": track_url,
                "artist": entry.get("uploader") or entry.get("channel") or "",
                "image": entry.get("thumbnail") or "",
                "duration": entry.get("duration"),
                "artist_url": url if "/sets/" not in url else None,
            }

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

