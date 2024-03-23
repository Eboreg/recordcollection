import math

from django.core.management.base import BaseCommand, CommandParser

from recordcollection.models import Album
from recordcollection.utils import (
    delete_orphan_artists, import_musicbrainz_genres,
)
from spotify.dataclasses import SpotifyAlbum, SpotifyUserAlbumsResponse
from spotify.request import spotify_get


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--delete", action="store_true", help="Delete orphan albums")
        parser.add_argument("--total", action="store_true", help="Total resync, not just add new items")

    def handle(self, *args, **options):
        album_ids = list(Album.objects.exclude(spotify_id=None).values_list("spotify_id", flat=True))

        import_musicbrainz_genres()
        user_albums = self.get_user_albums()
        if not options["total"]:
            user_albums = [a for a in user_albums if a.id not in album_ids]

        for idx, spotify_album in enumerate(user_albums):
            album_ids.append(spotify_album.id)
            album = spotify_album.to_album()
            print(f"[{idx + 1}/{len(user_albums)}] {album}")

        if options["delete"]:
            orphans = Album.objects.exclude(spotify_id=None).exclude(spotify_id__in=album_ids)
            if orphans:
                self.stdout.write(f"Deleting {orphans.count()} orphan albums.")
                orphans.delete()

        delete_orphan_artists()

    def get_user_albums(self) -> list[SpotifyAlbum]:
        albums = []
        page = 1
        pages: int | None = None
        uri: str | None = "https://api.spotify.com/v1/me/albums?limit=50"

        while uri is not None:
            self.stdout.write(f"Fetching data ({page}/{pages or '?'}) ...")
            response = SpotifyUserAlbumsResponse.from_dict(spotify_get(uri).json())
            if pages is None:
                pages = math.ceil(response.total / response.limit)
            page += 1
            albums.extend(response.items)
            uri = response.next

        return albums
