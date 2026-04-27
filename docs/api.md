# nuvem_de_som API

`nuvem_de_som` searches SoundCloud by scraping its public HTML pages and extracts audio streams via `yt-dlp`.

> **Note:** SoundCloud's HTML markup can change without notice. Stream extraction requires `yt-dlp` and an active internet connection.

## SoundCloud

All methods are static.

### `search(query, extract_streams=True)`

Combined search: yields tracks from the top people result, the top set result, and then individual tracks.

```python
from nuvem_de_som import SoundCloud

for track in SoundCloud.search("heavy metal", extract_streams=False):
    print(track["title"], track["url"])
```

### `search_tracks(query, extract_streams=True)`

Search by track name.

```python
for track in SoundCloud.search_tracks("piratech nuclear chill"):
    print(track)
```

### `search_people(query, extract_streams=True)`

Search by artist/user name. Each result is a dict with:
- `artist` — artist name
- `url` — profile URL
- `tracks` — list of track dicts for that artist

```python
for person in SoundCloud.search_people("piratech"):
    print(person["artist"])
    for t in person["tracks"]:
        print(" ", t["title"])
```

### `search_sets(query, extract_streams=True)`

Search for playlists/sets.

```python
for s in SoundCloud.search_sets("chill"):
    print(s["title"])
    for t in s["tracks"]:
        print(" ", t["title"])
```

### `get_tracks(url, extract_streams=False)`

Enumerate tracks on an artist page or set URL.

```python
for t in SoundCloud.get_tracks("https://soundcloud.com/piratech"):
    print(t["title"], t["url"])
```

## Track dict format

When `extract_streams=False`:
```python
{"title": str, "url": str}
```

When `extract_streams=True` (calls yt-dlp):
```python
{"title": str, "artist": str, "image": str, "url": str, "uri": str, "duration": int}
```

`uri` is the direct audio stream URL.

## `extract_streams` performance note

Each stream extraction makes an additional network request. For search results, pass `extract_streams=False` to get URLs quickly and call `_extract_streams(url)` lazily only when you need playback.
