from pprint import pprint

from django.core.management.base import BaseCommand, CommandParser

from spotify.functions import get_album


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        parser.add_argument("album_id")

    def handle(self, *args, **options):
        pprint(get_album(options["album_id"]))
