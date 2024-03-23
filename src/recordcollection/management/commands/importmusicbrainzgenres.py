from django.core.management.base import BaseCommand

from recordcollection.utils import import_musicbrainz_genres


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("Importing Musicbrainz genres ...", ending="")
        import_musicbrainz_genres()
        self.stdout.write(" done.")
