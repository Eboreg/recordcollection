import os
import time

import requests

from recordcollection.utils import get_user_agent


request_times: list[float] = []


def last_minute_request_times():
    return [t for t in request_times if t > (time.time() - 60.0)]


def discogs_get(url: str) -> requests.Response:
    api_key = os.environ.get("DISCOGS_API_KEY")
    api_secret = os.environ.get("DISCOGS_API_SECRET")
    times = last_minute_request_times()
    if len(times) > 60:
        sleep_seconds = times[0] - time.time() + 60.0
        time.sleep(sleep_seconds)
    headers = {
        "Authorization": f"Discogs key={api_key}, secret={api_secret}",
        "User-Agent": get_user_agent(),
    }
    response = requests.get(url, timeout=10, headers=headers)
    if response.status_code == 429:
        time.sleep(60.0)
        response = requests.get(
            url,
            timeout=10,
            headers={"Authorization": f"Discogs key={api_key}, secret={api_secret}"},
        )
    request_times.append(time.time())
    return response
