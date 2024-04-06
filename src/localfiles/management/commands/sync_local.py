import datetime
from glob import glob
from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser

from localfiles.functions import scan_directory_recursive
from recordcollection.models import Album, Track
from recordcollection.utils import get_env_datetime, import_musicbrainz_genres, set_env_datetime


class Command(BaseCommand):
    last_sync: datetime.datetime | None

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("path")
        parser.add_argument("--except", nargs="*", help="Path(s) to exclude")
        parser.add_argument("--various", action="store_true", help="All albums are various artists")
        parser.add_argument("--delete", action="store_true", help="Delete orphan albums")
        parser.add_argument("--total", action="store_true", help="Total resync, not just add new items")

    def handle(self, *args, **options):
        self.last_sync = get_env_datetime("LAST_LOCALFILES_SYNC")
        paths = [Path(path) for path in glob(options["path"])]
        exceptions = [Path(dir) for path in options["except"] or [] for dir in glob(path)]
        existing_file_paths = list(Track.objects.exclude(file_path=None).values_list("file_path", flat=True))
        file_paths: set[str] = set()

        import_musicbrainz_genres()

        for root in paths:
            file_paths.update(
                scan_directory_recursive(
                    directory=root,
                    exceptions=exceptions,
                    existing_file_paths=existing_file_paths,
                    is_compilation=options["various"],
                    total=options["total"],
                )
            )

        if options["delete"]:
            orphan_tracks = Track.objects.exclude(file_path=None).exclude(file_path__in=file_paths)
            if orphan_tracks:
                album_ids = [track.album_id for track in orphan_tracks if track.album_id is not None]
                self.stdout.write(f"Deleting {orphan_tracks.count()} orphan tracks.")
                orphan_tracks.delete()
                orphan_albums = Album.objects.filter(pk__in=album_ids, tracks=None)
                if orphan_albums:
                    self.stdout.write(f"Deleting {orphan_albums.count()} orphan albums.")
                    orphan_albums.delete()

        set_env_datetime("LAST_LOCALFILES_SYNC")
