from django.core.management.base import BaseCommand

from recordcollection.utils import import_musicbrainz_genres
from spotify.functions import get_user_albums_responses


class Command(BaseCommand):
    def handle(self, *args, **options):
        total: int | None = None
        idx = 0

        import_musicbrainz_genres()

        for response in get_user_albums_responses():
            total = response.total
            for spotify_album in response.items:
                album = spotify_album.to_album()
                if total is not None:
                    print(f"[{idx + 1}/{total}] {album}")
                else:
                    print(album)
                idx += 1
