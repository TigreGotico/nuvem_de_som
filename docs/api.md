# nuvem_de_som API

`nuvem_de_som` searches and streams SoundCloud content. Two implementation paths are available:

- **API v2 methods** (`*_api`, `get_tracks_full`, `resolve_user`) — use SoundCloud's internal API via yt-dlp's client_id management. Return full metadata (display name, artwork, duration) in one call. Preferred.
- **HTML scraper methods** (`search_tracks`, `search_people`, `search_sets`, `get_tracks`) — parse public HTML pages. No yt-dlp needed for metadata, but capped at ~20 results and return title + URL only. Kept for environments without yt-dlp and as fallback.

`search()` uses API v2 automatically and falls back to HTML scrapers if the API is unavailable.

> **Note:** SoundCloud's HTML markup and API responses can change without notice. Stream extraction always requires `yt-dlp`.

## SoundCloud

All methods are static.

---

## API v2 methods (preferred)

### `search_tracks_api(query, limit=10)`

Search tracks with full metadata — artwork, display name, duration — in one API call.

```python
from nuvem_de_som import SoundCloud

for track in SoundCloud.search_tracks_api("nuclear chill", limit=5):
    print(track["title"], track["artist"], track["duration"])
```

### `search_people_api(query, limit=10)`

Search artists/users with full metadata.

```python
for person in SoundCloud.search_people_api("acidkid"):
    print(person["artist"], person["artist_url"], person["image"])
```

### `search_playlists_api(query, limit=10)`

Search playlists/sets with full metadata.

```python
for pl in SoundCloud.search_playlists_api("chill"):
    print(pl["title"], pl["artist"], pl["image"])
```

### `resolve_user(profile_url)`

Resolve a profile URL to its real display name and avatar. Returns a dict or `None`.

```python
info = SoundCloud.resolve_user("https://soundcloud.com/acidkid")
# {"artist": "Piratech", "artist_url": "https://soundcloud.com/acidkid", "image": "..."}
```

### `get_tracks_full(url, limit=200)`

Enumerate **all** tracks for an artist page or set URL with full metadata.

Unlike `get_tracks()`, paginates through the complete catalogue via SoundCloud's API. Returns real display names, per-track artwork, and duration for every track.

```python
for t in SoundCloud.get_tracks_full("https://soundcloud.com/acidkid"):
    print(t["title"], t["artist"], t["duration"])

# Set/playlist URL
for t in SoundCloud.get_tracks_full("https://soundcloud.com/acidkid/sets/beathop"):
    print(t["title"])
```

---

## HTML scraper methods (fallback / no-yt-dlp)

These methods parse SoundCloud's public HTML. They require no API client_id but are capped at ~20 results and only return `title` + `url` (no artwork or duration unless `extract_streams=True`).

### `search_tracks(query, extract_streams=True)`

```python
for track in SoundCloud.search_tracks("acidkid", extract_streams=False):
    print(track["title"], track["url"])
```

### `search_people(query, extract_streams=True)`

Each result: `{"artist", "url", "tracks"}` where `tracks` is from `get_tracks()`.

```python
for person in SoundCloud.search_people("acidkid", extract_streams=False):
    print(person["artist"], person["url"])
```

### `search_sets(query, extract_streams=True)`

Each result: `{"title", "url", "tracks"}`.

```python
for s in SoundCloud.search_sets("chill", extract_streams=False):
    print(s["title"])
```

### `get_tracks(url, extract_streams=False)`

Scrapes the first ~20 tracks from an artist or set page.

```python
for t in SoundCloud.get_tracks("https://soundcloud.com/acidkid"):
    print(t["title"], t["url"])
```

---

## Combined entrypoint

### `search(query, extract_streams=True)`

Yields tracks from artist results, set results, and direct track search. Uses API v2 automatically; falls back to HTML scrapers if unavailable. `extract_streams` is only used on the HTML fallback path.

```python
for track in SoundCloud.search("heavy metal", extract_streams=False):
    print(track["title"], track["url"])
```

---

## Dict formats

**API v2 track** (`search_tracks_api`, `get_tracks_full`):
```python
{
    "title": str,
    "url": str,           # SoundCloud permalink
    "artist": str,        # display name (e.g. "Piratech", not slug "acidkid")
    "artist_url": str,    # artist profile URL
    "image": str,         # artwork URL (falls back to user avatar)
    "duration": int | None,  # seconds
}
```

**API v2 artist** (`search_people_api`, `resolve_user`):
```python
{"artist": str, "artist_url": str, "image": str}
```

**API v2 playlist** (`search_playlists_api`):
```python
{"title": str, "url": str, "artist": str, "artist_url": str, "image": str}
```

**HTML track** (`search_tracks`, `get_tracks`) with `extract_streams=False`:
```python
{"title": str, "url": str}
```

**HTML track** with `extract_streams=True` (calls yt-dlp):
```python
{"title": str, "artist": str, "image": str, "url": str, "uri": str, "duration": int}
```

`uri` is the direct audio stream URL, only present with `extract_streams=True`.

## Stream extraction

`_extract_streams(url)` resolves a track URL to its direct audio stream via yt-dlp. Call it lazily at playback time — not during search.
