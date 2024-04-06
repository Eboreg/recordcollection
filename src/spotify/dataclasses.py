import datetime
import functools
import operator
import re
from dataclasses import dataclass
from typing import Any, Literal

from django.db.models import Q
from django.db.models.functions import Lower

from recordcollection.abstract_classes import AbstractBaseRecord
from recordcollection.models import (
    Album,
    AlbumArtist,
    Artist,
    Genre,
    Track,
    TrackArtist,
)
from spotify.abstract_classes import AbstractSpotifyResponse
from spotify.request import get_spotify_response


@dataclass
class SpotifyArtist(AbstractBaseRecord):
    id: str
    name: str

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "name" and isinstance(value, str):
            return value.strip()
        return super().serialize_field(key, value)

    def to_artist(self) -> Artist:
        return Artist.iupdate_or_create(name=self.name, spotify_id=self.id)


@dataclass
class SpotifyImage(AbstractBaseRecord):
    height: int
    url: str
    width: int


@dataclass
class SpotifyTrack(AbstractBaseRecord):
    artists: list[SpotifyArtist]
    disc_number: int
    duration_ms: int
    id: str
    name: str
    track_number: int

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "artists":
            return [SpotifyArtist.from_dict(d) for d in value]
        if key == "name" and isinstance(value, str):
            return value.strip()
        return super().serialize_field(key, value)

    def to_track(self, album_id: int | None = None, year: int | None = None) -> Track:
        track = Track.objects.update_or_create(
            album_id=album_id,
            disc_number=self.disc_number,
            track_number=self.track_number,
            defaults={
                "spotify_id": self.id,
                "title": self.name,
                "year": year,
                "duration": datetime.timedelta(seconds=round(self.duration_ms / 1000)),
            }
        )[0]
        for artist_idx, artist in enumerate(self.artists):
            TrackArtist.objects.update_or_create(
                track=track,
                artist=artist.to_artist(),
                defaults={"position": artist_idx},
            )

        return track


@dataclass
class SpotifyAlbum(AbstractBaseRecord):
    @dataclass
    class Tracks(AbstractBaseRecord):
        items: list[SpotifyTrack]
        limit: int
        offset: int
        total: int
        previous: str | None = None
        next: str | None = None

        @classmethod
        def serialize_field(cls, key: str, value: Any):
            if key == "items":
                return [SpotifyTrack.from_dict(d) for d in value]
            return super().serialize_field(key, value)

    album_type: Literal["album", "single", "compilation"]
    artists: list[SpotifyArtist]
    genres: list[str]
    id: str
    images: list[SpotifyImage]
    name: str
    release_date: str
    total_tracks: int
    tracks: Tracks

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "tracks":
            return cls.Tracks.from_dict(value)
        if key == "images":
            return [SpotifyImage.from_dict(d) for d in value]
        if key == "artists":
            return [SpotifyArtist.from_dict(d) for d in value]
        if key == "name" and isinstance(value, str):
            return value.strip()
        return super().serialize_field(key, value)

    def to_album(self) -> Album:
        year_match = re.match(r"^(\d{4})", self.release_date)
        year = int(year_match.group(1)) if year_match else None
        artist_names = [a.name for a in self.artists]
        is_compilation = self.album_type == "compilation" and "Various Artists" in artist_names

        album_qs = Album.objects.filter(
            Q(spotify_id=None) | Q(spotify_id=self.id),
            title__iexact=self.name,
            medium=Album.Medium.STREAMING,
        )
        if is_compilation:
            album_qs = album_qs.filter(is_compilation=True)
        elif artist_names:
            album_qs = album_qs.filter(
                functools.reduce(operator.or_, [Q(artists__name__iexact=name) for name in artist_names], Q())
            )

        album = album_qs.first()

        if album:
            album.spotify_id = self.id
            album.is_compilation = is_compilation
            if year and not album.year:
                album.year = year
            album.save(update_fields=["spotify_id", "year", "is_compilation"])
        else:
            album = Album.objects.create(
                spotify_id=self.id,
                title=self.name,
                medium=Album.Medium.STREAMING,
                year=year,
                is_compilation=is_compilation,
            )

        tracks = self.tracks
        while tracks is not None:
            for track in tracks.items:
                track.to_track(album_id=album.id, year=year if self.album_type != "compilation" else None)
            if tracks.next:
                tracks = get_spotify_response(url=tracks.next, response_type=SpotifyTracksResponse)
            else:
                tracks = None

        if self.genres:
            genres = list(
                Genre.objects
                .annotate(name_lower=Lower("name"))
                .filter(name_lower__in=self.genres)
            )
            if genres:
                album.genres.add(*genres)

        if not is_compilation:
            for artist_idx, artist in enumerate(self.artists):
                AlbumArtist.objects.update_or_create(
                    album=album,
                    artist=artist.to_artist(),
                    defaults={"position": artist_idx},
                )

        return album


@dataclass
class SpotifyUserAlbum(AbstractBaseRecord):
    album: SpotifyAlbum
    added_at: datetime.datetime

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "added_at":
            return datetime.datetime.fromisoformat(value)
        if key == "album":
            return SpotifyAlbum.from_dict(value)
        return super().serialize_field(key, value)


@dataclass
class SpotifyTracksResponse(AbstractSpotifyResponse[SpotifyTrack]):
    @classmethod
    def serialize_item(cls, value: Any) -> SpotifyTrack:
        return SpotifyTrack.from_dict(value)


@dataclass
class SpotifyUserAlbumsResponse(AbstractSpotifyResponse[SpotifyUserAlbum]):
    @classmethod
    def serialize_item(cls, value: Any) -> SpotifyUserAlbum:
        return SpotifyUserAlbum.from_dict(value)
