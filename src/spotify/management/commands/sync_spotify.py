import datetime
import math

from django.core.management.base import BaseCommand, CommandParser

from recordcollection.models import Album
from recordcollection.utils import (
    delete_orphan_artists,
    get_env_datetime,
    import_musicbrainz_genres,
    set_env_datetime,
)
from spotify.dataclasses import SpotifyAlbum, SpotifyUserAlbumsResponse
from spotify.request import get_spotify_response


class Command(BaseCommand):
    last_sync: datetime.datetime | None

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--delete", action="store_true", help="Delete orphan albums")
        parser.add_argument("--total", action="store_true", help="Total resync, not just add new items")

    def handle(self, *args, **options):
        self.last_sync = get_env_datetime("LAST_SPOTIFY_SYNC")
        album_ids = list(Album.objects.exclude(spotify_id=None).values_list("spotify_id", flat=True))
        total = options["total"] is True

        import_musicbrainz_genres()
        user_albums = self.get_user_albums(total)
        if not total:
            user_albums = [a for a in user_albums if a.id not in album_ids]

        for idx, spotify_album in enumerate(user_albums):
            album_ids.append(spotify_album.id)
            album = spotify_album.to_album()
            album = album.update_from_musicbrainz()
            print(f"[{idx + 1}/{len(user_albums)}] {album}")

        if options["delete"]:
            orphans = Album.objects.exclude(spotify_id=None).exclude(spotify_id__in=album_ids)
            if orphans:
                self.stdout.write(f"Deleting {orphans.count()} orphan albums.")
                orphans.delete()

        set_env_datetime("LAST_SPOTIFY_SYNC")
        delete_orphan_artists()

    def get_user_albums(self, total: bool = False) -> list[SpotifyAlbum]:
        albums = []
        page = 1
        pages: int | None = None
        uri: str | None = "https://api.spotify.com/v1/me/albums?limit=50"

        while uri is not None:
            if total or not self.last_sync:
                self.stdout.write(f"Fetching data (page {page}/{pages or '?'}) ...")
            else:
                self.stdout.write(f"Fetching data (page {page}) ...")
            response = get_spotify_response(url=uri, response_type=SpotifyUserAlbumsResponse)
            if pages is None:
                pages = math.ceil(response.total / response.limit)
            page += 1
            albums.extend([item.album for item in response.items])
            if response.items and not total and self.last_sync and response.items[-1].added_at < self.last_sync:
                uri = None
            else:
                uri = response.next

        return albums
