from django.core.management.base import BaseCommand, CommandParser

from spotify.functions import get_spotify_track


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        parser.add_argument("id_or_url")
        parser.add_argument("--codeorder", "-c", action="store_true", help="Order by code instead of country name")

    def handle(self, *args, **options):
        if isinstance(options["id_or_url"], str):
            track = get_spotify_track(track_id_or_link=options["id_or_url"])
            if track.artist_string:
                self.stdout.write(f"{track.artist_string} - {track.name}", ending="\n\n")
            else:
                self.stdout.write(track.name, ending="\n\n")
            self.stdout.write("Available markets")
            self.stdout.write("-----------------")

            for market in track.get_localized_available_markets(codeorder=options["codeorder"]):
                self.stdout.write(str(market))
