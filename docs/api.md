# nuvem_de_som API

`nuvem_de_som` searches, streams, and downloads SoundCloud content.

## Architecture

```
SoundCloudBase  (abstract)
├── SoundCloudAPI    — internal API v2, full metadata, recommended
├── SoundCloudHTML   — HTML scraper, no extra deps
├── SoundCloudYTDLP  — yt-dlp backed, best stream resolution
└── SoundCloud       — orchestrator subclass, tries API → yt-dlp → HTML
```

All backends implement the same interface.  All track dicts share the same
canonical key schema regardless of backend:

```python
{
    "title":      str,        # track title
    "url":        str,        # SoundCloud permalink
    "artist":     str,        # display name ("" when not available)
    "artist_url": str,        # profile URL  ("" when not available)
    "image":      str,        # artwork URL  ("" when not available)
    "duration":   int | None, # seconds      (None when not available)
}
```

> **Note:** `SoundCloudYTDLP.search_people()` and `search_sets()` yield nothing —
> yt-dlp has no people/set search endpoint.
>
> `SoundCloudHTML.search_tracks()` / `search_people()` / `search_sets()` return
> limited metadata from SoundCloud's search HTML (title + URL only); use
> `get_tracks()` on an artist/set page for full metadata including duration.

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

Uses SoundCloud's internal API v2.  Returns full metadata in one call.
Requires only `requests` — no yt-dlp for search, listing, or stream resolution.

```python
from nuvem_de_som import SoundCloudAPI

sc = SoundCloudAPI()

# Track search
for t in sc.search_tracks("nuclear chill", limit=5):
    print(t["title"], t["artist"], t["duration"])

# People search
for p in sc.search_people("acidkid"):
    print(p["artist"], p["artist_url"], p["image"])

# Playlist/set search
for pl in sc.search_sets("chill", limit=5):
    print(pl["title"], pl["artist"])

# Enumerate all tracks for an artist or set (paginates the full catalogue)
for t in sc.get_tracks("https://soundcloud.com/acidkid", limit=200):
    print(t["title"])

for t in sc.get_tracks("https://soundcloud.com/acidkid/sets/beathop"):
    print(t["title"])

# Resolve a track URL to a direct stream (no yt-dlp required)
stream_url = sc.resolve_stream("https://soundcloud.com/acidkid/nuclear-chill")
stream_url = sc.resolve_stream("...", prefer="hls")    # default: "progressive"

# Resolve a profile URL to display name + avatar
user = sc.resolve_user("https://soundcloud.com/acidkid")
# {"artist": "Piratech", "artist_url": "...", "image": "..."}
```

---

## SoundCloudHTML (no-dep fallback)

Parses SoundCloud's public HTML.  No API key.

- **Artist / set pages** (`get_tracks()`): extracts full metadata including
  artist, artist_url, and duration from schema.org `MusicRecording` markup —
  no extra requests, no yt-dlp.
- **Search pages** (`search_tracks()`, `search_people()`, `search_sets()`):
  SoundCloud's search HTML is sparse — only title + URL are available.
  Use `search_tracks_enriched()` to add metadata at the cost of one extra
  request per track.

```python
from nuvem_de_som import SoundCloudHTML

sc = SoundCloudHTML()

# Artist page — full metadata from schema.org markup
for t in sc.get_tracks("https://soundcloud.com/acidkid", limit=20):
    print(t["title"], t["artist"], t["duration"])  # duration in seconds

# Search — title + URL only (artist/artist_url/image/duration are ""/None)
for t in sc.search_tracks("nuclear chill", limit=5):
    print(t["title"], t["url"])

# Enriched search — adds artist + image via one extra request per track
for t in sc.search_tracks_enriched("nuclear chill", limit=5):
    print(t["title"], t.get("artist"))

# resolve_user scrapes Open Graph / JSON-LD (no API required)
user = sc.resolve_user("https://soundcloud.com/acidkid")

# resolve_stream raises NotImplementedError — HTML has no stream access
# Use SoundCloudAPI or SoundCloudYTDLP for stream resolution
```

---

## SoundCloudYTDLP (last resort)

All operations backed by yt-dlp.  Best stream resolution resilience; slower.
No people or set search.  Requires `pip install nuvem_de_som[streams]`.

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

## Downloads

Download methods are available **only** on `SoundCloudYTDLP` and `SoundCloud`
(the orchestrator).  `SoundCloudAPI` and `SoundCloudHTML` do **not** expose
download methods — calling them would silently lack any implementation.

Downloads require yt-dlp: `pip install nuvem_de_som[streams]`.

`download_track()` returns `None` on failure (not a placeholder path).
`download_tracks()` returns only the paths of successfully downloaded files —
failed downloads are omitted from the list.

`SoundCloud` (orchestrator) delegates all download calls to its internal
`SoundCloudYTDLP` backend automatically.

```python
# Use either SoundCloudYTDLP directly, or the SoundCloud orchestrator
from nuvem_de_som import SoundCloud, SoundCloudYTDLP

sc = SoundCloud()        # orchestrator — download delegates to yt-dlp backend
# sc = SoundCloudYTDLP() # yt-dlp backend directly

# Single track → ~/Music/Artist - Title.mp3
path = sc.download_track(
    "https://soundcloud.com/acidkid/some-track",
    output_dir="~/Music",
    audio_format="mp3",   # or "aac", "flac", etc.
)

# Multiple tracks — only successful downloads in the return list
paths = sc.download_tracks(
    ["https://soundcloud.com/acidkid/track-a",
     "https://soundcloud.com/acidkid/track-b"],
    output_dir="~/Music",
)

# Full artist page or set → ~/Music/Piratech/Title.mp3
sc.download_playlist("https://soundcloud.com/acidkid", output_dir="~/Music")
sc.download_playlist("https://soundcloud.com/acidkid/sets/beathop", output_dir="~/Music")
```

> **Note:** Calling `download_track()` / `download_tracks()` / `download_playlist()`
> on `SoundCloudAPI` or `SoundCloudHTML` will raise `AttributeError` — those
> backends do not expose download methods.

---

## Dict schemas

### Track (all backends)

```python
{
    "title":      str,
    "url":        str,        # SoundCloud permalink
    "artist":     str,        # display name; "" when not available
    "artist_url": str,        # profile URL; "" when not available
    "image":      str,        # artwork URL; "" when not available
    "duration":   int | None, # seconds; None when not available
}
```

> `SoundCloudHTML.search_*` methods return `""` / `None` for artist, artist_url,
> image, and duration — those fields are absent from SoundCloud's search HTML.
> `get_tracks()` on an artist/set page provides all fields.

### Artist (`search_people`, `resolve_user`)

```python
{"artist": str, "artist_url": str, "image": str}
```

### Playlist (`search_sets`)

```python
{"title": str, "url": str, "artist": str, "artist_url": str, "image": str}
```

---

## Stream resolution

`resolve_stream(track_url, prefer="progressive")` resolves a permalink to a
direct audio URL.

- `prefer="progressive"` — direct MP3/AAC, seekable (default)
- `prefer="hls"` — HLS playlist (`.m3u8`)

Any value other than `"progressive"` or `"hls"` raises `ValueError`.

```python
url = sc.resolve_stream("https://soundcloud.com/acidkid/nuclear-chill")
url = sc.resolve_stream("...", prefer="hls")
```

## Logging

The library logs debug-level messages via the standard `logging` module under
the `nuvem_de_som` logger.  Enable with:

```python
import logging
logging.getLogger("nuvem_de_som").setLevel(logging.DEBUG)
```
