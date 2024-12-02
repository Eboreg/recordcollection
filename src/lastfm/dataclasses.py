from dataclasses import dataclass
from typing import Any

from recordcollection.abstract_classes import AbstractBaseRecord


@dataclass
class LastFmTopTrack(AbstractBaseRecord):
    @dataclass
    class Artist(AbstractBaseRecord):
        name: str
        mbid: str | None
        url: str

        @classmethod
        def serialize_field(cls, key: str, value: Any):
            if key == "mbid":
                return value if value else None
            return super().serialize_field(key, value)

    name: str
    playcount: int
    mbid: str | None
    url: str
    artist: Artist
    duration: int

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "artist":
            return cls.Artist.from_dict(value)
        if key == "mbid":
            return value if value else None
        if key == "playcount":
            return int(value)
        if key == "duration":
            duration = int(value)
            if duration > 0:
                return duration
            return None
        return super().serialize_field(key, value)


@dataclass
class LastFmTopTracksResponse(AbstractBaseRecord):
    @dataclass
    class TopTracks(AbstractBaseRecord):
        @dataclass
        class Attr(AbstractBaseRecord):
            user: str
            total_pages: int
            page: int
            total: int
            per_page: int

            @classmethod
            def key_to_attr(cls, key: str) -> str:
                if key == "totalPages":
                    return "total_pages"
                if key == "perPage":
                    return "per_page"
                return super().key_to_attr(key)

            @classmethod
            def serialize_field(cls, key: str, value: Any):
                if key in ("totalPages", "page", "total", "perPage"):
                    return int(value)
                return super().serialize_field(key, value)

        track: list[LastFmTopTrack]
        attr: Attr

        @classmethod
        def key_to_attr(cls, key: str) -> str:
            if key == "@attr":
                return "attr"
            return super().key_to_attr(key)

        @classmethod
        def serialize_field(cls, key: str, value: Any):
            if key == "track":
                return [LastFmTopTrack.from_dict(d) for d in value]
            if key == "@attr":
                return cls.Attr.from_dict(value)
            return super().serialize_field(key, value)

    toptracks: TopTracks

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "toptracks":
            return cls.TopTracks.from_dict(value)
        return super().serialize_field(key, value)
