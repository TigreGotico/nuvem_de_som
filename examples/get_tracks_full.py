"""List all tracks on a SoundCloud artist or set page.

Uses get_tracks_full() which paginates through the full catalogue via
SoundCloud's internal API (yt-dlp flat extraction) instead of being limited
to the ~20 items visible in the initial HTML page.

Usage:
    python get_tracks_full.py https://soundcloud.com/acidkid
    python get_tracks_full.py https://soundcloud.com/acidkid/sets/acid 50
"""
import sys
from nuvem_de_som import SoundCloud

url = sys.argv[1] if len(sys.argv) > 1 else "https://soundcloud.com/acidkid"
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 200

print(f"Fetching tracks for: {url}  (limit={limit})\n")
for i, track in enumerate(SoundCloud.get_tracks_full(url, limit=limit), 1):
    duration = f"  [{int(track['duration']//60)}:{int(track['duration']%60):02d}]" if track.get("duration") else ""
    print(f"{i:3}. {track['title']}{duration}")
    print(f"     {track['url']}")
