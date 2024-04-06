import os

from discogs.dataclasses import (
    DiscogsMasterRelease,
    DiscogsRelease,
    DiscogsUserReleasesResponse,
)
from discogs.request import discogs_get


def get_user_release_response(page: int, per_page: int = 100) -> DiscogsUserReleasesResponse:
    username = os.environ.get("DISCOGS_USERNAME")
    url = f"https://api.discogs.com/users/{username}/collection/folders/0/releases?per_page={per_page}&page={page}"
    response = discogs_get(url)
    return DiscogsUserReleasesResponse.from_dict(response.json())


def get_release(release_id: int) -> DiscogsRelease:
    url = f"https://api.discogs.com/releases/{release_id}"
    response = discogs_get(url)
    return DiscogsRelease.from_dict(response.json())


def get_master_release(master_id: int) -> DiscogsMasterRelease:
    url = f"https://api.discogs.com/masters/{master_id}"
    response = discogs_get(url)
    return DiscogsMasterRelease.from_dict(response.json())
