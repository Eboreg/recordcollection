from urllib.parse import quote

from musicbrainz.dataclasses import (
    MusicBrainzRelease,
    MusicBrainzReleaseSearch,
)
from musicbrainz.request import musicbrainz_get
from recordcollection.models import Album


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
