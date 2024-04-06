from collections.abc import Iterator

from spotify.dataclasses import SpotifyAlbum, SpotifyUserAlbumsResponse
from spotify.request import get_spotify_response, spotify_get


def get_user_albums() -> list[SpotifyAlbum]:
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


def get_album(album_id: str) -> SpotifyAlbum:
    uri = f"https://api.spotify.com/v1/albums/{album_id}"
    response = spotify_get(uri)
    return SpotifyAlbum.from_dict(response.json())
