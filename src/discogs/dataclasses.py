import datetime
import functools
import math
import operator
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from django.db.models import Q
from django.db.models.functions import Lower

from recordcollection.abstract_classes import AbstractBaseRecord
from recordcollection.models import (
    Album, AlbumArtist, Artist, Genre, Track, TrackArtist,
)


@dataclass
class DiscogsPagination(AbstractBaseRecord):
    @dataclass
    class Urls(AbstractBaseRecord):
        last: str | None = None
        next: str | None = None

    items: int
    page: int
    pages: int
    per_page: int
    urls: Urls

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "urls":
            return cls.Urls.from_dict(value)
        return super().serialize_field(key, value)


@dataclass
class DiscogsArtist(AbstractBaseRecord):
    anv: str
    id: int
    join: str
    name: str
    resource_url: str
    role: str
    tracks: str

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "name" and isinstance(value, str):
            return re.sub(r" \(\d+\)$", "", value).strip()
        return super().serialize_field(key, value)

    def to_artist(self) -> Artist:
        return Artist.iupdate_or_create(name=self.name, discogs_id=self.id)


@dataclass
class DiscogsFormat(AbstractBaseRecord):
    name: Literal["CD", "Vinyl", "Box Set"]
    qty: str
    descriptions: list[str] = field(default_factory=list)


@dataclass
class DiscogsUserRelease(AbstractBaseRecord):
    @dataclass
    class BasicInformation(AbstractBaseRecord):
        artists: list[DiscogsArtist]
        cover_image: str
        formats: list[DiscogsFormat]
        genres: list[str]
        id: int
        master_id: int
        master_url: str | None
        resource_url: str
        styles: list[str]
        thumb: str
        title: str
        year: int

        @classmethod
        def serialize_field(cls, key: str, value: Any):
            if key == "artists":
                return [DiscogsArtist.from_dict(d) for d in value]
            if key == "formats":
                return [DiscogsFormat.from_dict(d) for d in value]
            return super().serialize_field(key, value)

    basic_information: BasicInformation
    date_added: str
    id: int
    instance_id: int
    rating: int

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "basic_information":
            return cls.BasicInformation.from_dict(value)
        return super().serialize_field(key, value)


@dataclass
class DiscogsUserReleasesResponse(AbstractBaseRecord):
    pagination: DiscogsPagination
    releases: list[DiscogsUserRelease]

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            pagination=DiscogsPagination.from_dict(d["pagination"]),
            releases=[DiscogsUserRelease.from_dict(dd) for dd in d["releases"]],
        )


@dataclass
class DiscogsImage(AbstractBaseRecord):
    height: int
    resource_url: str
    type: str
    uri: str
    uri150: str
    width: int


@dataclass
class DiscogsTrack(AbstractBaseRecord):
    duration: str
    position: str
    title: str
    artists: list[DiscogsArtist] = field(default_factory=list)
    extraartists: list[DiscogsArtist] = field(default_factory=list)

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key in ("artists", "extraartists"):
            return [DiscogsArtist.from_dict(d) for d in value]
        if key == "title" and isinstance(value, str):
            return value.strip()
        return super().serialize_field(key, value)

    def to_track(self, album_id: int, disc_number: int, track_number: int) -> Track:
        duration: datetime.timedelta | None = None

        duration_match = re.match(r"(?:(\d+):)?(\d+):(\d\d)$", self.duration)
        if duration_match:
            hours, minutes, seconds = duration_match.groups()
            if hours:
                duration = datetime.timedelta(
                    hours=float(hours),
                    minutes=float(minutes),
                    seconds=float(seconds),
                )
            elif minutes:
                duration = datetime.timedelta(minutes=float(minutes), seconds=float(seconds))
            elif seconds:
                duration = datetime.timedelta(seconds=float(seconds))

        track = Track.objects.update_or_create(
            album_id=album_id,
            track_number=track_number,
            disc_number=disc_number,
            defaults={
                "title": self.title,
                "duration": duration,
            },
        )[0]
        for artist_idx, artist in enumerate(self.artists):
            TrackArtist.objects.update_or_create(
                track=track,
                artist=artist.to_artist(),
                defaults={"join_phrase": artist.join, "position": artist_idx},
            )

        return track


@dataclass
class DiscogsRelease(AbstractBaseRecord):
    artists: list[DiscogsArtist]
    artists_sort: str
    data_quality: str
    date_added: str
    date_changed: str
    estimated_weight: int
    extraartists: list[DiscogsArtist]
    format_quantity: int
    formats: list[DiscogsFormat]
    genres: list[str]
    id: int
    lowest_price: float
    num_for_sale: int
    resource_url: str
    status: str
    thumb: str
    title: str
    tracklist: list[DiscogsTrack]
    uri: str

    country: str | None = None
    images: list[DiscogsImage] = field(default_factory=list)
    master_id: int | None = None
    master_url: str | None = None
    notes: str | None = None
    released: int | None = None
    released_formatted: str | None = None
    styles: list[str] = field(default_factory=list)
    year: int | None = None

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key in ("artists", "extraartists"):
            return [DiscogsArtist.from_dict(d) for d in value]
        if key == "formats":
            return [DiscogsFormat.from_dict(d) for d in value]
        if key == "images":
            return [DiscogsImage.from_dict(d) for d in value]
        if key == "tracklist":
            return [DiscogsTrack.from_dict(d) for d in value]
        if key == "title" and isinstance(value, str):
            return value.strip()
        return super().serialize_field(key, value)

    def get_medium(self) -> Album.Medium | None:
        if any(f.name == "CD" for f in self.formats):
            return Album.Medium.CD
        if any(f.name == "Vinyl" for f in self.formats):
            return Album.Medium.VINYL
        return None

    def get_disc_and_track_number(self, track: DiscogsTrack) -> tuple[int, int]:
        disc_number = 1
        track_number: int | None = None

        disc_track_match = re.match(r"^(\d+)-(\d+)$", track.position)
        if disc_track_match:
            disc_number, track_number = [int(g) for g in disc_track_match.groups()]

        side_track_match = re.match(r"^([A-Z])(\d+)$", track.position)
        if side_track_match:
            side_number = ord(side_track_match.group(1)) - 64
            disc_number = math.ceil(side_number / 2)
            track_number = int(side_track_match.group(2))
            if side_number % 2 == 0:
                previous_side = chr(side_number + 63)
                previous_side_tracks = [t for t in self.tracklist if t.position.startswith(previous_side)]
                track_number += len(previous_side_tracks)

        if track_number is None:
            track_number = self.tracklist.index(track) + 1

        return disc_number, track_number

    def to_album(self) -> Album:
        is_compilation = self.artists_sort.lower() == "various"
        medium = self.get_medium()
        artist_names = [a.name for a in self.artists]
        genres_and_styles = self.genres + self.styles

        album_qs = Album.objects.filter(title__iexact=self.title)
        if medium:
            album_qs = album_qs.filter(medium=medium)
        if is_compilation:
            album_qs = album_qs.filter(is_compilation=True)
        elif artist_names:
            album_qs = album_qs.filter(
                functools.reduce(operator.or_, [Q(artists__name__iexact=name) for name in artist_names], Q())
            )

        album = album_qs.first()

        if album:
            album.discogs_id = self.id
            album.is_compilation = is_compilation
            album.medium = medium or album.medium
            if album.year is None and self.year and self.year > 0:
                album.year = self.year
            album.save(update_fields=["discogs_id", "year", "is_compilation", "medium"])
        else:
            album = Album.objects.create(
                discogs_id=self.id,
                title=self.title,
                year=self.year if self.year and self.year > 0 else None,
                is_compilation=is_compilation,
                medium=medium,
            )

        for track in self.tracklist:
            disc_number, track_number = self.get_disc_and_track_number(track)
            track.to_track(
                album_id=album.id,
                disc_number=disc_number,
                track_number=track_number,
            )

        if genres_and_styles:
            genres = list(
                Genre.objects
                .annotate(name_lower=Lower("name"))
                .filter(name_lower__in=[g.lower() for g in genres_and_styles])
            )
            if genres:
                album.genres.add(*genres)

        if not is_compilation:
            for artist_idx, artist in enumerate(self.artists):
                AlbumArtist.objects.update_or_create(
                    album=album,
                    artist=artist.to_artist(),
                    defaults={"join_phrase": artist.join, "position": artist_idx},
                )

        return album


@dataclass
class DiscogsMasterRelease(AbstractBaseRecord):
    artists: list[DiscogsArtist]
    data_quality: str
    genres: list[str]
    id: str
    images: list[DiscogsImage]
    lowest_price: float
    main_release_url: str
    main_release: int
    num_for_sale: int
    resource_url: str
    styles: list[str]
    title: str
    tracklist: list[DiscogsTrack]
    uri: str
    year: int

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "artists":
            return [DiscogsArtist.from_dict(d) for d in value]
        if key == "images":
            return [DiscogsImage.from_dict(d) for d in value]
        if key == "tracklist":
            return [DiscogsTrack.from_dict(d) for d in value]
        return super().serialize_field(key, value)
