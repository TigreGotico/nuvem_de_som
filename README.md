# nuvem_de_som

SoundCloud search, stream, and download client. Three independent backends, one orchestrator, one terminal app.

## Install

```bash
pip install nuvem_de_som           # search + stream (no yt-dlp)
pip install "nuvem_de_som[yt-dlp]" # adds yt-dlp for download & stream fallback
pip install "nuvem_de_som[cli]"    # adds the nds terminal app
pip install "nuvem_de_som[yt-dlp,cli]"  # everything
```

## Terminal app — `nds`

```bash
nds search "nuclear chill"          # interactive: pick a track, then play or download
nds browse https://soundcloud.com/acidkid   # browse artist page interactively
nds play   https://soundcloud.com/acidkid/piratech-nuclear-chill
nds download https://soundcloud.com/acidkid/piratech-nuclear-chill -o ~/Music
nds download https://soundcloud.com/acidkid --playlist -o ~/Music

nds --backend api search "chill"    # force a specific backend (api/html/ytdlp/auto)
```

Playback uses `--player` / `NDS_PLAYER` env var, or auto-detects: **mpv** → vlc → ffplay → mplayer → afplay → cvlc.
Any binary name or full path works — Termux, Windows, macOS all supported.

## Python API — quick start

```python
from nuvem_de_som import SoundCloud, SoundCloudAPI, SoundCloudHTML, SoundCloudYTDLP

sc = SoundCloud()        # orchestrator: API → yt-dlp → HTML fallback (recommended)
sc = SoundCloudAPI()     # API only — full metadata, no yt-dlp required
sc = SoundCloudHTML()    # HTML scraper — no extra deps
sc = SoundCloudYTDLP()   # yt-dlp only

# Search
for t in sc.search_tracks("nuclear chill", limit=5):
    print(t["title"], t["artist"], t["duration"])  # duration in seconds

# Browse an artist or set page
for t in sc.get_tracks("https://soundcloud.com/acidkid", limit=50):
    print(t["title"])

# Resolve a direct stream URL (no yt-dlp)
url = sc.resolve_stream("https://soundcloud.com/acidkid/piratech-nuclear-chill")
url = sc.resolve_stream("...", prefer="hls")   # or "progressive" (default)

# Download — SoundCloudAPI uses pure requests; SoundCloudYTDLP uses yt-dlp
path = sc.download_track("https://soundcloud.com/acidkid/piratech-nuclear-chill",
                          output_dir="~/Music")
sc.download_playlist("https://soundcloud.com/acidkid", output_dir="~/Music")
```

All track dicts share the same schema regardless of backend:

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

## Backends

| Backend | Search | Stream | Download | Extra dep |
|---|---|---|---|---|
| `SoundCloudAPI` | ✅ full metadata | ✅ | ✅ pure requests | — |
| `SoundCloudHTML` | ⚠️ title+URL only | ❌ | ❌ | — |
| `SoundCloudYTDLP` | ✅ | ✅ | ✅ yt-dlp | `yt-dlp` |
| `SoundCloud` | ✅ API→yt-dlp→HTML | ✅ | ✅ API first | optional `yt-dlp` |

> `SoundCloudHTML.search_*` returns only title + URL from SoundCloud's search HTML.
> Use `get_tracks()` on an artist/set page for full metadata, or `search_tracks_enriched()`
> for one extra request per result.

## Docs

- [Full API reference](docs/api.md)
