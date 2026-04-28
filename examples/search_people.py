"""Search SoundCloud for artists and list their tracks."""
import sys
from nuvem_de_som import SoundCloud

query = sys.argv[1] if len(sys.argv) > 1 else "acidkid"

print(f"Artists for: {query!r}\n")
for person in SoundCloud.search_people(query, extract_streams=False):
    print(f"Artist: {person['artist']}  {person['url']}")
    for t in person["tracks"][:5]:
        print(f"  - {t['title']}  {t['url']}")
    print()
