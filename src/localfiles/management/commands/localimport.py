from glob import glob
from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser

from localfiles.functions import scan_file_system
from recordcollection.utils import import_musicbrainz_genres


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        parser.add_argument("path")
        parser.add_argument("--except", nargs="*")
        parser.add_argument("--various", action="store_true")

    def handle(self, *args, **options):
        paths = glob(options["path"])
        exceptions = [Path(dir) for path in options["except"] or [] for dir in glob(path)]
        import_musicbrainz_genres()
        scan_file_system(
            roots=[Path(path) for path in paths],
            exceptions=exceptions,
            all_is_compilation=options["various"],
        )
