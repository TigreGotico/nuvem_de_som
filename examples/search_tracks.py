"""Search SoundCloud tracks (no stream extraction — just URLs)."""
import sys
from nuvem_de_som import SoundCloud

query = sys.argv[1] if len(sys.argv) > 1 else "ambient"

sc = SoundCloud()
print(f"Tracks for: {query!r}\n")
for track in sc.search_tracks(query, limit=10):
    print(f"  {track['title']}  →  {track['url']}")
