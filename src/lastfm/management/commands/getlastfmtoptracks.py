from django.core.management.base import BaseCommand
from django.db.models import Q

from lastfm.functions import iterate_user_top_tracks
from recordcollection.models import Track


class Command(BaseCommand):
    def handle(self, *args, **options):
        for lastfm_track in iterate_user_top_tracks():
            track_qs = Track.objects.none()
            if lastfm_track.mbid:
                track_qs = Track.objects.filter(musicbrainz_id=lastfm_track.mbid)
            if track_qs.count() == 0 and lastfm_track.artist.mbid:
                track_qs = Track.objects.filter(
                    Q(artists__musicbrainz_id=lastfm_track.artist.mbid) |
                    Q(album__artists__musicbrainz_id=lastfm_track.artist.mbid),
                    title__iexact=lastfm_track.name,
                )
            if track_qs.count() == 0:
                track_qs = Track.objects.filter(
                    Q(artists__name__iexact=lastfm_track.artist.name) |
                    Q(album__artists__name__iexact=lastfm_track.artist.name),
                    title__iexact=lastfm_track.name,
                )
            tracks = list(track_qs)
            if len(tracks) > 0:
                for track in tracks:
                    track.play_count = lastfm_track.playcount
                    if lastfm_track.mbid:
                        track.musicbrainz_id = lastfm_track.mbid
                self.stdout.write(
                    f"{lastfm_track.artist.name} - {lastfm_track.name}: "
                    f"updating {len(tracks)} tracks ({lastfm_track.playcount} plays)"
                )
                Track.objects.bulk_update(tracks, fields=["play_count", "musicbrainz_id"])
