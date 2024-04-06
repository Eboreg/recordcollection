import datetime
import re
from dataclasses import dataclass
from typing import Any

import Levenshtein
from django.db import transaction
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


def date_to_year(date: str | None) -> int | None:
    if date:
        year = date.split("-")[0]
        if re.match(r"^\d{4}$", year):
            return int(year)
    return None


@dataclass
class MusicBrainzArtistCredit(AbstractBaseRecord):
    @dataclass
    class MusicBrainzArtist(AbstractBaseRecord):
        id: str
        name: str

        def get_levenshtein_ratio(self, other: str) -> float:
            return Levenshtein.ratio(self.name.lower(), other.lower())

    artist: MusicBrainzArtist
    name: str
    joinphrase: str = " / "

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "artist":
            return cls.MusicBrainzArtist.from_dict(value)
        return super().serialize_field(key, value)

    def to_artist(self) -> Artist:
        return Artist.iupdate_or_create(name=self.name, musicbrainz_id=self.artist.id)


class MusicBrainzArtistCreditList(list[MusicBrainzArtistCredit]):
    def __str__(self):
        out = ""
        for idx, credit in enumerate(self):
            out += credit.name
            if idx < len(self) - 1:
                out += credit.joinphrase
        return out

    @classmethod
    def from_dicts(cls, dicts: list[dict]) -> "MusicBrainzArtistCreditList":
        return cls([MusicBrainzArtistCredit.from_dict(d) for d in dicts])

    def get_levenshtein_ratio(self, other: list[str]) -> float:
        ratios = []

        for name in other:
            highest = 0.0
            for credit in self:
                ratio = credit.artist.get_levenshtein_ratio(name)
                if ratio > highest:
                    highest = ratio
            ratios.append(highest)

        return sum(ratios, start=0.0) / len(ratios) if len(ratios) > 0 else 0.0


@dataclass
class MusicBrainzGenre(AbstractBaseRecord):
    id: str
    name: str


@dataclass
class MusicBrainzTrack(AbstractBaseRecord):
    @dataclass
    class Recording(AbstractBaseRecord):
        genres: list[MusicBrainzGenre]
        first_release_date: str | None = None
        length: int | None = None

        @classmethod
        def serialize_field(cls, key: str, value: Any):
            if key == "genres":
                return [MusicBrainzGenre.from_dict(d) for d in value]
            return super().serialize_field(key, value)

    artist_credit: MusicBrainzArtistCreditList
    id: str
    number: str
    position: int
    recording: Recording
    title: str
    length: int | None

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "artist-credit":
            return MusicBrainzArtistCreditList.from_dicts(value)
        if key == "recording":
            return cls.Recording.from_dict(value)
        return super().serialize_field(key, value)

    def get_duration(self) -> datetime.timedelta | None:
        length = self.length or self.recording.length
        if length:
            return datetime.timedelta(seconds=round(length / 1000))
        return None

    def get_genres(self) -> list[str]:
        return [g.name for g in self.recording.genres]

    def get_year(self) -> int | None:
        return date_to_year(self.recording.first_release_date)

    def get_levenshtein_ratio(self, track: Track) -> float:
        result = Levenshtein.ratio(self.title.lower(), track.title.lower())
        result += self.artist_credit.get_levenshtein_ratio([artist.name for artist in track.artists.all()])
        return result / 2


@dataclass
class MusicBrainzRelease(AbstractBaseRecord):
    @dataclass
    class ReleaseGroup(AbstractBaseRecord):
        artist_credit: MusicBrainzArtistCreditList
        id: str
        title: str
        genres: list[MusicBrainzGenre]
        first_release_date: str | None = None

        @classmethod
        def serialize_field(cls, key: str, value: Any):
            if key == "artist-credit":
                return MusicBrainzArtistCreditList.from_dicts(value)
            if key == "genres":
                return [MusicBrainzGenre.from_dict(d) for d in value]
            return super().serialize_field(key, value)

    @dataclass
    class Media(AbstractBaseRecord):
        position: int
        track_count: int
        track_offset: int
        tracks: list[MusicBrainzTrack]

        @classmethod
        def serialize_field(cls, key: str, value: Any):
            if key == "tracks":
                return [MusicBrainzTrack.from_dict(d) for d in value]
            return super().serialize_field(key, value)

    @dataclass
    class ReleaseTrack(MusicBrainzTrack):
        disc_number: int

        def update_track(self, track: Track) -> Track:
            track.musicbrainz_id = self.id
            track.title = self.title
            track.disc_number = self.disc_number
            track.track_number = self.position
            track.year = self.get_year()
            track.duration = track.duration or self.get_duration()
            track.save(update_fields=["musicbrainz_id", "title", "disc_number", "track_number", "year", "duration"])
            track.artists.clear()

            for artist_idx, artist in enumerate(self.artist_credit):
                TrackArtist.objects.create(
                    track=track,
                    artist=artist.to_artist(),
                    join_phrase=artist.joinphrase,
                    position=artist_idx,
                )

            if self.recording.genres:
                genres = list(
                    Genre.objects
                    .annotate(name_lower=Lower("name"))
                    .filter(name_lower__in=[g.name.lower() for g in self.recording.genres])
                )
                if genres:
                    track.genres.add(*genres)

            return track

    @dataclass
    class AlbumMatch:
        album: Album
        release: "MusicBrainzRelease"
        ratio: float

    artist_credit: MusicBrainzArtistCreditList
    id: str
    title: str
    release_group: ReleaseGroup
    media: list[Media]
    genres: list[MusicBrainzGenre]
    date: str | None = None

    def __str__(self):
        if self.artist_credit:
            return f"{self.artist_credit} - {self.title} ({self.id})"
        return f"{self.title} ({self.id})"

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "release-group":
            return cls.ReleaseGroup.from_dict(value)
        if key == "artist-credit":
            return MusicBrainzArtistCreditList.from_dicts(value)
        if key == "media":
            return [cls.Media.from_dict(d) for d in value]
        if key == "genres":
            return [MusicBrainzGenre.from_dict(d) for d in value]
        return super().serialize_field(key, value)

    def get_genres(self) -> set[str]:
        return set([
            *[g.name for g in self.genres],
            *[g.name for g in self.release_group.genres],
            *[g for m in self.media for t in m.tracks for g in t.get_genres()],
        ])

    def get_tracks(self) -> list[ReleaseTrack]:
        return [
            self.ReleaseTrack(disc_number=m.position, **track.to_dict())
            for m in self.media
            for track in m.tracks
        ]

    def get_year(self) -> int | None:
        return date_to_year(self.release_group.first_release_date)

    def get_levenshtein_ratio(self, album: Album) -> float:
        """
        Title and artist ratios weigh as much as all track ratios together.
        """
        ratios = [Levenshtein.ratio(self.title.lower(), album.title.lower())]
        album_tracks = list(album.tracks.all())
        own_tracks = self.get_tracks()
        track_ratios = []

        if not album.is_compilation:
            ratios.append(self.artist_credit.get_levenshtein_ratio([artist.name for artist in album.artists.all()]))

        for mb_track, track in zip(own_tracks, album_tracks):
            track_ratios.append(mb_track.get_levenshtein_ratio(track))
        if len(own_tracks) < len(album_tracks):
            track_ratios += [1.0] * (len(album_tracks) - len(own_tracks))
        if len(track_ratios) > 0:
            ratios.append(sum(track_ratios, start=0.0) / len(track_ratios))

        return sum(ratios, start=0.0) / len(ratios)

    def get_album_match(self, album: Album) -> AlbumMatch:
        return self.AlbumMatch(album=album, release=self, ratio=self.get_levenshtein_ratio(album))

    @transaction.atomic
    def update_album(self, album: Album) -> Album:
        album.title = self.title
        album.year = self.get_year()
        album.musicbrainz_id = self.id
        album.musicbrainz_group_id = self.release_group.id
        album.save(update_fields=["title", "year", "musicbrainz_id", "musicbrainz_group_id"])

        if self.get_genres():
            genres = list(
                Genre.objects
                .annotate(name_lower=Lower("name"))
                .filter(name_lower__in=[g.lower() for g in self.get_genres()])
            )
            if genres:
                album.genres.add(*genres)

        if not album.is_compilation:
            album.artists.clear()
            for artist_idx, artist in enumerate(self.artist_credit):
                AlbumArtist.objects.create(
                    album=album,
                    artist=artist.to_artist(),
                    join_phrase=artist.joinphrase,
                    position=artist_idx,
                )

        for mb_track, track in zip(self.get_tracks(), album.tracks.all()):
            mb_track.update_track(track)

        return album


@dataclass
class MusicBrainzReleaseSearch(AbstractBaseRecord):
    @dataclass
    class Release(AbstractBaseRecord):
        @dataclass
        class ReleaseGroup(AbstractBaseRecord):
            title: str
            id: str

        artist_credit: MusicBrainzArtistCreditList
        release_group: ReleaseGroup
        id: str
        title: str

        @classmethod
        def serialize_field(cls, key: str, value: Any):
            if key == "release-group":
                return cls.ReleaseGroup.from_dict(value)
            if key == "artist-credit":
                return MusicBrainzArtistCreditList.from_dicts(value)
            return super().serialize_field(key, value)

        def get_levenshtein_ratio(self, album: Album) -> float:
            ratios = [Levenshtein.ratio(self.title.lower(), album.title.lower())]
            if not album.is_compilation:
                ratios.append(
                    self.artist_credit.get_levenshtein_ratio([artist.name for artist in album.artists.all()])
                )
            return sum(ratios, start=0.0) / len(ratios)

    count: int
    offset: int
    releases: list[Release]

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "releases":
            return [cls.Release.from_dict(d) for d in value]
        return super().serialize_field(key, value)
