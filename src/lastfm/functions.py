import os
from typing import Iterator
import requests

from lastfm.dataclasses import LastFmTopTrack, LastFmTopTracksResponse


def get_user_top_tracks() -> LastFmTopTracksResponse:
    username = os.environ.get("LASTFM_USERNAME")
    api_key = os.environ.get("LASTFM_API_KEY")
    url = (
        "https://ws.audioscrobbler.com/2.0/?method=user.gettoptracks"
        f"&user={username}&api_key={api_key}&format=json&limit=1000"
    )
    response = requests.get(url, timeout=10)
    return LastFmTopTracksResponse.from_dict(response.json())


def iterate_user_top_tracks() -> Iterator[LastFmTopTrack]:
    page: int | None = 1
    username = os.environ.get("LASTFM_USERNAME")
    api_key = os.environ.get("LASTFM_API_KEY")
    while page is not None:
        url = (
            "https://ws.audioscrobbler.com/2.0/?method=user.gettoptracks"
            f"&user={username}&api_key={api_key}&format=json&limit=1000&page={page}"
        )
        response = LastFmTopTracksResponse.from_dict(requests.get(url, timeout=10).json())
        for track in response.toptracks.track:
            yield track
        if response.toptracks.attr.total_pages > page:
            page += 1
        else:
            page = None
