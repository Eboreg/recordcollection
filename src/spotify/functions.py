import re
from collections.abc import Iterator

from spotify.dataclasses import (
    SpotifyAlbum,
    SpotifyTrack,
    SpotifyUserAlbumsResponse,
)
from spotify.request import get_spotify_response, spotify_get


def get_spotify_user_albums() -> list[SpotifyAlbum]:
    albums = []
    uri: str | None = "https://api.spotify.com/v1/me/albums?limit=50"

    while uri is not None:
        response = get_spotify_response(url=uri, response_type=SpotifyUserAlbumsResponse)
        albums.extend([item.album for item in response.items])
        uri = response.next

    return albums


def iterate_user_albums_responses() -> Iterator[SpotifyUserAlbumsResponse]:
    uri: str | None = "https://api.spotify.com/v1/me/albums?limit=50"

    while uri is not None:
        response = SpotifyUserAlbumsResponse.from_dict(spotify_get(uri).json())
        yield response
        uri = response.next


def get_spotify_album(album_id: str) -> SpotifyAlbum:
    uri = f"https://api.spotify.com/v1/albums/{album_id}"
    response = spotify_get(uri)
    return SpotifyAlbum.from_dict(response.json())


def get_spotify_track(track_id_or_link: str) -> SpotifyTrack:
    track_id: str
    if is_spotify_track_link(track_id_or_link):
        track_id = get_spotify_track_id_from_link(track_id_or_link)
    else:
        track_id = track_id_or_link
    uri = f"https://api.spotify.com/v1/tracks/{track_id}"
    response = spotify_get(uri)
    return SpotifyTrack.from_dict(response.json())


def is_spotify_track_link(value: str) -> bool:
    return value.startswith("https://open.spotify.com/track/")


def get_spotify_track_id_from_link(link: str) -> str:
    match = re.match(r"^https://open.spotify.com/track/([^?]*).*$", string=link)
    if match:
        return match.group(1)
    raise ValueError(f"Not a valid Spotify track link: {link}")
