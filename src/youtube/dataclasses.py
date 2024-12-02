import re
from dataclasses import dataclass, field
from typing import Any

import Levenshtein

from recordcollection.abstract_classes import AbstractBaseRecord
from spotify.dataclasses import SpotifyTrack


@dataclass
class YoutubeVideo(AbstractBaseRecord):
    id: str
    title: str
    duration_ms: int | None = None
    metadata: "YoutubeMetadata | None" = None

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "metadata":
            return YoutubeMetadata.from_dict(value)
        return super().serialize_field(key, value)

    @property
    def web_url(self) -> str:
        return f"https://youtu.be/{self.id}"

    def match_spotify_track(self, spotify_track: SpotifyTrack) -> float:
        """Scale 0.0 - 1.0, the higher the better match."""
        matched_artists = [
            artist.name for artist in spotify_track.artists
            if artist.name.lower() in self.title.lower()
        ]
        stripped_title = self.title
        for artist in matched_artists:
            stripped_title = re.sub(rf"[ ,\-&]*{artist}[ ,\-&]*", "", stripped_title, flags=re.IGNORECASE)
        title_score = Levenshtein.ratio(stripped_title.strip().lower(), spotify_track.name.lower())
        artist_score = float(len(matched_artists)) / len(spotify_track.artists)
        if self.metadata:
            ms_diff = abs(spotify_track.duration_ms - self.metadata.duration_ms)
            ms_diff_ratio = ms_diff / spotify_track.duration_ms
            duration_score = max(1.0 - ms_diff_ratio, 0.0)
            return ((title_score + artist_score) / 2) * duration_score
        return (title_score + artist_score) / 2


@dataclass
class YoutubeMetadata(AbstractBaseRecord):
    bitrate: int
    sample_rate: int
    url: str
    duration_ms: int
    raw_mime_type: str
    mime_type: str = field(init=False)
    codecs: list[str] | None = field(init=False, default_factory=list)

    def __post_init__(self):
        mime_type = self.raw_mime_type.split(";")[0]
        match = re.match(r"^.*codecs=\"?([^\"]*)\"?$", self.raw_mime_type)
        if match:
            self.codecs = list(match.groups())
        if mime_type == "audio/webm" and self.codecs:
            self.mime_type = f"audio/{self.codecs[0]}"
        else:
            self.mime_type = mime_type

    @property
    def file_extension(self) -> str:
        return self.mime_type.split("/")[-1]

    @property
    def quality(self) -> int:
        return self.bitrate * self.sample_rate
