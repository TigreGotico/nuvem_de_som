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

