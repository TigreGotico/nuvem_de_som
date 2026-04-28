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
for track in SoundCloud.search_tracks("acidkid"):
    print(track)
```

### `search_people(query, extract_streams=True)`

Search by artist/user name. Each result is a dict with:
- `artist` — artist name
- `url` — profile URL
- `tracks` — list of track dicts for that artist

```python
for person in SoundCloud.search_people("acidkid"):
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

Enumerate tracks on an artist page or set URL by scraping the HTML.

```python
for t in SoundCloud.get_tracks("https://soundcloud.com/acidkid"):
    print(t["title"], t["url"])
```

**Limitation:** SoundCloud renders its pages with JavaScript. The initial HTML only contains ~20 items; `get_tracks()` cannot paginate beyond that. Use `get_tracks_full()` when you need the complete catalogue.

### `get_tracks_full(url, limit=200)`

Enumerate **all** tracks on an artist page or set URL using SoundCloud's API v2.

Unlike `get_tracks()`, this method paginates through the complete catalogue via SoundCloud's internal API (client_id auto-managed by yt-dlp, refreshed on expiry). Each yielded dict always contains `title`, `url`, `artist`, `artist_url`, `image`, and `duration` keys — including the artist's real display name (e.g. `"Piratech"` rather than the URL slug `"acidkid"`), per-track artwork, and duration in seconds.

```python
for t in SoundCloud.get_tracks_full("https://soundcloud.com/acidkid"):
    print(t["title"], t["url"])

# Cap at 50 tracks
tracks = list(SoundCloud.get_tracks_full("https://soundcloud.com/acidkid", limit=50))
```

Works for both artist profile URLs and set (playlist) URLs:

```python
for t in SoundCloud.get_tracks_full("https://soundcloud.com/acidkid/sets/acid"):
    print(t["title"])
```

## Track dict format

`get_tracks()` with `extract_streams=False`:
```python
{"title": str, "url": str}
```

`get_tracks()` with `extract_streams=True` (calls yt-dlp):
```python
{"title": str, "artist": str, "image": str, "url": str, "uri": str, "duration": int}
```

`get_tracks_full()` (always):
```python
{
    "title": str,        # track title
    "url": str,          # SoundCloud permalink
    "artist": str,       # display name (e.g. "Piratech", not URL slug "acidkid")
    "artist_url": str,   # artist profile permalink
    "image": str,        # artwork URL (falls back to user avatar if no track art)
    "duration": int | None,  # seconds
}
```

`uri` (direct audio stream URL) is only present in `extract_streams=True` results; it is **not** in `get_tracks_full()` output — obtain it lazily via `_extract_streams(url)` at playback time.

## `extract_streams` performance note

Each stream extraction makes an additional network request. For search results, pass `extract_streams=False` to get URLs quickly and call `_extract_streams(url)` lazily only when you need playback.
