import time

import requests

from recordcollection.utils import get_user_agent


last_request_time: float | None = None


def musicbrainz_get(path: str, params: dict[str, str] | None = None) -> requests.Response:
    from musicbrainz import request  # pylint: disable=import-self

    path = path.lstrip("/")
    params = params or {}
    params["fmt"] = "json"
    url = f"https://musicbrainz.org/ws/2/{path}"
    headers = {"User-Agent": get_user_agent()}
    now = time.time()

    if request.last_request_time and now - request.last_request_time < 1:
        sleep_seconds = 1 - now + request.last_request_time
        time.sleep(sleep_seconds)

    request.last_request_time = time.time()

    return requests.get(url=url, params=params, headers=headers, timeout=10)
