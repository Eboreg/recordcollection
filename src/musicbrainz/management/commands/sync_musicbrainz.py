from django.core.management.base import BaseCommand, CommandParser

from musicbrainz.functions import get_best_musicbrainz_album_match
from recordcollection.models import Album
from recordcollection.utils import (
    delete_orphan_artists,
    import_musicbrainz_genres,
)


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--retry", action="store_true", help="Retry previously failing matches")
        parser.add_argument("--total", action="store_true", help="Re-sync previously synced albums")

    def handle(self, *args, **options):
        import_musicbrainz_genres()

        albums = Album.prefetched()
        if not options["total"]:
            albums = albums.filter(musicbrainz_id=None)
            if not options["retry"]:
                albums = albums.exclude(musicbrainz_id="")

        for album in albums:
            match = get_best_musicbrainz_album_match(album)
            if match and match.ratio >= 0.8:
                self.stdout.write(f"{repr(album)}: Matched with {match.release} (ratio={match.ratio})")
                match.release.update_album(match.album)
            else:
                if match:
                    self.stdout.write(f"{repr(album)}: Too low ratio for {match.release} (ratio={match.ratio})")
                else:
                    self.stdout.write(f"{repr(album)}: No match found")
                album.musicbrainz_id = ""
                album.save(update_fields=["musicbrainz_id"])

        delete_orphan_artists()
