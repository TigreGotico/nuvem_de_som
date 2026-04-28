# nuvem_de_som API

`nuvem_de_som` searches, streams, and downloads SoundCloud content.

## Architecture

```
SoundCloudBase  (abstract)
├── SoundCloudAPI    — internal API v2, full metadata, recommended
├── SoundCloudHTML   — HTML scraper, ~20 results, no extra deps
├── SoundCloudYTDLP  — yt-dlp backed, best stream resolution
└── SoundCloud       — orchestrator subclass, tries backends in order
```

All backends implement the same interface:
- `search_tracks(query, limit)` / `search_people(query, limit)` / `search_sets(query, limit)`
- `get_tracks(url, limit)`
- `resolve_stream(track_url, prefer)` → `str | None`
- `resolve_user(profile_url)` → `dict | None`
- `search(query, limit)` — combined (inherited from base)
- `download_track(url, output_dir, audio_format)` — requires yt-dlp
- `download_tracks(urls, output_dir, audio_format)` — requires yt-dlp
- `download_playlist(url, output_dir, audio_format)` — requires yt-dlp

> **Note:** `SoundCloudYTDLP.search_people()` and `search_sets()` yield nothing — yt-dlp has no people/set search endpoint.

---

## Quick start

```python
from nuvem_de_som import SoundCloud, SoundCloudAPI, SoundCloudHTML, SoundCloudYTDLP

sc = SoundCloud()        # orchestrator: API → yt-dlp → HTML fallback
sc = SoundCloudAPI()     # API only (full metadata, recommended)
sc = SoundCloudHTML()    # HTML scraper only (no extra deps)
sc = SoundCloudYTDLP()   # yt-dlp only (requires pip install nuvem_de_som[streams])

for t in sc.search_tracks("nuclear chill", limit=5):
    print(t["title"], t["artist"], t["duration"])
```

---

## SoundCloudAPI (recommended)

Uses SoundCloud's internal API v2. Returns full metadata in one call.
Requires only `requests` — no yt-dlp for search, listing, or stream resolution.

```python
from nuvem_de_som import SoundCloudAPI

sc = SoundCloudAPI()

# Search
for t in sc.search_tracks("nuclear chill", limit=5):
    print(t["title"], t["artist"], t["duration"])

for p in sc.search_people("acidkid", limit=5):
    print(p["artist"], p["artist_url"])

for pl in sc.search_sets("chill", limit=5):
    print(pl["title"], pl["artist"])

# Enumerate all tracks for an artist or set
for t in sc.get_tracks("https://soundcloud.com/acidkid", limit=200):
    print(t["title"])

for t in sc.get_tracks("https://soundcloud.com/acidkid/sets/beathop"):
    print(t["title"])

# Resolve
stream_url = sc.resolve_stream("https://soundcloud.com/acidkid/track-slug")
user = sc.resolve_user("https://soundcloud.com/acidkid")
# {"artist": "Piratech", "artist_url": "...", "image": "..."}
```

---

## SoundCloudHTML (fallback / no-dep)

Parses SoundCloud's public HTML. No API key. Results capped at ~20 per page;
returns `title` + `url` only (no artwork or duration).

```python
from nuvem_de_som import SoundCloudHTML

sc = SoundCloudHTML()

for t in sc.search_tracks("acidkid", limit=10):
    print(t["title"], t["url"])

# Enriched: one extra request per track for artist + image
for t in sc.search_tracks_enriched("acidkid", limit=5):
    print(t["title"], t.get("artist"), t.get("image"))

# resolve_user scrapes Open Graph / JSON-LD (no API)
user = sc.resolve_user("https://soundcloud.com/acidkid")

# resolve_stream uses yt-dlp if installed, else returns None
stream = sc.resolve_stream("https://soundcloud.com/acidkid/track-slug")
```

---

## SoundCloudYTDLP (last resort)

All operations backed by yt-dlp. Best stream resolution resilience; slower.
No people or set search. Requires `pip install nuvem_de_som[streams]`.

```python
from nuvem_de_som import SoundCloudYTDLP

sc = SoundCloudYTDLP()

for t in sc.search_tracks("nuclear chill", limit=5):
    print(t["title"])

for t in sc.get_tracks("https://soundcloud.com/acidkid"):
    print(t["title"])

stream = sc.resolve_stream("https://soundcloud.com/acidkid/track-slug")
```

---

## Downloads (all backends)

Download methods are inherited by all backends and use yt-dlp internally.
Requires `pip install nuvem_de_som[streams]`.

```python
sc = SoundCloud()

# Single track → ~/Music/Artist - Title.mp3
sc.download_track(
    "https://soundcloud.com/acidkid/some-track",
    output_dir="~/Music",
    audio_format="mp3",
)

# Multiple tracks
sc.download_tracks(
    ["https://soundcloud.com/acidkid/track-a", "https://soundcloud.com/acidkid/track-b"],
    output_dir="~/Music",
)

# Full artist page or playlist → ~/Music/Piratech/
sc.download_playlist(
    "https://soundcloud.com/acidkid",
    output_dir="~/Music",
)
sc.download_playlist(
    "https://soundcloud.com/acidkid/sets/beathop",
    output_dir="~/Music",
)
```

---

## Dict formats

**API track** (`SoundCloudAPI.search_tracks`, `SoundCloudAPI.get_tracks`):
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

**API artist** (`SoundCloudAPI.search_people`, `SoundCloudAPI.resolve_user`):
```python
{"artist": str, "artist_url": str, "image": str}
```

**API playlist** (`SoundCloudAPI.search_sets`):
```python
{"title": str, "url": str, "artist": str, "artist_url": str, "image": str}
```

**HTML track** (`SoundCloudHTML.search_tracks`, `SoundCloudHTML.get_tracks`):
```python
{"title": str, "url": str}
```

**HTML artist** (`SoundCloudHTML.search_people`):
```python
{"artist": str, "artist_url": str, "url": str, "image": str, "tracks": list[dict]}
```

**yt-dlp track** (`SoundCloudYTDLP`):
```python
{
    "title": str,
    "url": str,
    "artist": str,
    "artist_url": str,
    "image": str,
    "duration": int | None,
}
```
