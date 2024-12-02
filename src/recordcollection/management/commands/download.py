import dataclasses

import requests
from django.core.management.base import BaseCommand, CommandParser

from recordcollection.utils import sanitize_filename
from spotify.functions import (
    get_spotify_track,
    get_spotify_track_id_from_link,
    is_spotify_track_link,
)
from youtube.clients import YoutubeAndroidTestSuiteClient, YoutubeWebClient


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--spotify", "-s")
        group.add_argument("--discogs", "-d")
        group.add_argument("--musicbrainz", "-m")

    def handle(self, *args, **options):
        if options["spotify"]:
            track_id: str
            if is_spotify_track_link(options["spotify"]):
                track_id = get_spotify_track_id_from_link(options["spotify"])
            else:
                track_id = options["spotify"]
            self.download_spotify_track(track_id)
        elif options["discogs"]:
            self.stdout.write("Not implemented yet.")
        elif options["musicbrainz"]:
            self.stdout.write("Not implemented yet.")

    def download_spotify_track(self, track_id: str):
        spotify_track = get_spotify_track(track_id)
        query = f"{spotify_track.artist_string} {spotify_track.name}".strip()
        videos = [
            dataclasses.replace(video, metadata=YoutubeAndroidTestSuiteClient().get_best_metadata(video.id))
            for video in YoutubeWebClient().get_video_search_results(query)
        ]
        video_matches = sorted(
            [(video, video.match_spotify_track(spotify_track)) for video in videos],
            key=lambda m: m[1],
            reverse=True,
        )
        if video_matches and video_matches[0][1] >= 0.9:
            video, score = video_matches[0]
            assert video.metadata is not None

            basename = sanitize_filename(
                f"{spotify_track.artist_string} - {spotify_track.name}"
                if spotify_track.artist_string
                else spotify_track.name
            )
            filename = f"{basename}.{video.metadata.file_extension}"

            self.stdout.write(f"Best match: {video.title} ({video.web_url}) (score: {score})")
            response = requests.get(video.metadata.url, stream=True, timeout=None)

            if response.ok:
                length = int(response.headers["Content-Length"]) if "Content-Length" in response.headers else None
                i = 1
                last_percent = -1

                with open(filename, "wb") as f:
                    for chunk in response.iter_content(chunk_size=10_000):
                        percent = round(((i * 10_000) / length) * 100) if length else None
                        if percent is not None and percent > last_percent:
                            self.stdout.write(f"\r{percent:3}% " + ("*" * percent), ending="")
                        f.write(chunk)
                        i += 1

                self.stdout.write(f"\nTrack was saved as {filename}.")

            response.close()
