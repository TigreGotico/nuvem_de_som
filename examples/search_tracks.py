"""Search SoundCloud tracks (no stream extraction — just URLs)."""
import sys
from nuvem_de_som import SoundCloud

query = sys.argv[1] if len(sys.argv) > 1 else "ambient"

print(f"Tracks for: {query!r}\n")
for i, track in enumerate(SoundCloud.search_tracks(query, extract_streams=False)):
    print(f"  {track['title']}  →  {track['url']}")
    if i >= 9:
        break
