"""Search SoundCloud for artists and list their top tracks."""
import sys
from nuvem_de_som import SoundCloud

query = sys.argv[1] if len(sys.argv) > 1 else "acidkid"

sc = SoundCloud()
print(f"Artists for: {query!r}\n")
for person in sc.search_people(query, limit=5):
    print(f"Artist: {person['artist']}  {person['artist_url']}")
    if person.get("artist_url"):
        for t in list(sc.get_tracks(person["artist_url"], limit=5)):
            print(f"  - {t['title']}  {t['url']}")
    print()
