import datetime

from django.core.management.base import BaseCommand, CommandParser

from discogs.dataclasses import DiscogsUserRelease
from discogs.functions import get_release, get_user_release_response
from recordcollection.models import Album
from recordcollection.utils import (
    delete_orphan_artists,
    get_env_datetime,
    import_musicbrainz_genres,
    set_env_datetime,
)


class Command(BaseCommand):
    last_sync: datetime.datetime | None

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--delete", action="store_true", help="Delete orphan albums")
        parser.add_argument("--total", action="store_true", help="Total resync, not just add new items")

    def handle(self, *args, **options):
        self.last_sync = get_env_datetime("LAST_DISCOGS_SYNC")
        release_ids = list(Album.objects.exclude(discogs_id=None).values_list("discogs_id", flat=True))

        import_musicbrainz_genres()
        user_releases = self.get_user_releases()
        if not options["total"]:
            user_releases = [r for r in user_releases if r.basic_information.id not in release_ids]

        for idx, user_release in enumerate(user_releases):
            release_ids.append(user_release.basic_information.id)
            release = get_release(user_release.basic_information.id)
            album = release.to_album()
            album = album.update_from_musicbrainz()
            print(f"[{idx + 1}/{len(user_releases)}] {album}")

        if options["delete"]:
            orphans = Album.objects.exclude(discogs_id=None).exclude(discogs_id__in=release_ids)
            if orphans:
                self.stdout.write(f"Deleting {orphans.count()} orphan albums.")
                orphans.delete()

        set_env_datetime("LAST_DISCOGS_SYNC")
        delete_orphan_artists()

    def get_user_releases(self) -> list[DiscogsUserRelease]:
        page = 1
        pages: int | None = None
        user_releases = []

        while pages is None or page <= pages:
            self.stdout.write(f"Fetching data ({page}/{pages or '?'}) ...")
            response = get_user_release_response(page)
            pages = response.pagination.pages
            page += 1
            user_releases.extend(response.releases)

        return user_releases
