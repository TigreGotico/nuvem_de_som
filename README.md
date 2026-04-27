# nuvem_de_som

SoundCloud search and stream extractor. Scrapes SoundCloud's public HTML and uses `yt-dlp` for audio stream extraction.

## Install

```bash
pip install nuvem_de_som
```

## Quick start

```python
from nuvem_de_som import SoundCloud

# Search tracks (fast, no stream extraction)
for track in SoundCloud.search_tracks("ambient", extract_streams=False):
    print(track["title"], track["url"])

# Search with streams (slower, uses yt-dlp)
for track in SoundCloud.search_tracks("ambient", extract_streams=True):
    print(track["title"], track["uri"])  # uri = playable audio URL
```

## Docs

- [API reference](docs/api.md)

## Examples

See the [`examples/`](examples/) directory.
