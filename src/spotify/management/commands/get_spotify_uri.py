import json

from django.core.management.base import BaseCommand, CommandParser

from spotify.request import spotify_get


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        parser.add_argument("uri")

    def handle(self, *args, **options):
        j = spotify_get(options["uri"]).json()
        jj = json.dumps(j, indent=4)
        print(jj)
