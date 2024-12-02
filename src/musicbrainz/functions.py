import time
from urllib.parse import quote

import requests

from musicbrainz.dataclasses import (
    MusicBrainzRelease,
    MusicBrainzReleaseSearch,
)
from recordcollection.models import Album
from recordcollection.utils import get_user_agent


last_request_time: float | None = None


def musicbrainz_get(path: str, params: dict[str, str] | None = None) -> requests.Response:
    from musicbrainz import functions  # pylint: disable=import-self

    path = path.lstrip("/")
    params = params or {}
    params["fmt"] = "json"
    url = f"https://musicbrainz.org/ws/2/{path}"
    headers = {"User-Agent": get_user_agent()}
    now = time.time()

    if functions.last_request_time and now - functions.last_request_time < 1:
        sleep_seconds = 1 - now + functions.last_request_time
        time.sleep(sleep_seconds)

    functions.last_request_time = time.time()

    return requests.get(url=url, params=params, headers=headers, timeout=10)


def get_musicbrainz_release(release_id: str) -> MusicBrainzRelease | None:
    try:
        response = musicbrainz_get(
            path=f"release/{release_id}",
            params={"inc": "recordings artist-credits genres release-groups"},
        )
        return MusicBrainzRelease.from_dict(response.json())
    except Exception as e:
        print(e)
        return None


def get_musicbrainz_album_matches(album: Album) -> list[MusicBrainzRelease.AlbumMatch]:
    search_params = {"release": album.title, "tracks": str(album.tracks.count())}
    album_artist = album.artist_string()
    if album_artist:
        search_params["artist"] = album_artist
    query = " AND ".join([f"{k}:{quote(v)}" for k, v in search_params.items()])
    path = f"release?query={query}&limit=10"

    try:
        response = musicbrainz_get(path=path)
        result = MusicBrainzReleaseSearch.from_dict(response.json())
        releases = [get_musicbrainz_release(r.id) for r in result.releases]
        matches = [release.get_album_match(album) for release in releases if release is not None]
        return sorted(matches, key=lambda m: m.ratio, reverse=True)
    except Exception as e:
        print(f"Error for album ID={album.id}: {e}")
        return []


def get_best_musicbrainz_album_match(album: Album) -> MusicBrainzRelease.AlbumMatch | None:
    matches = get_musicbrainz_album_matches(album=album)
    return matches[0] if matches else None
