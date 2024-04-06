import base64
import datetime
import os
import sys
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Type, TypeVar
from urllib.parse import parse_qs, urlparse

import requests
from django.utils import timezone

from recordcollection.abstract_classes import AbstractBaseRecord
from spotify.abstract_classes import AbstractSpotifyResponse
from spotify.models import SpotifyAccessToken


ABR = TypeVar("ABR", bound=AbstractBaseRecord)


REDIRECT_HOST = "localhost"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}"


def get_token_request_headers():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    b64_client = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    return {
        "Authorization": f"Basic {b64_client}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def save_access_token(token: dict) -> SpotifyAccessToken:
    return SpotifyAccessToken.objects.create(
        access_token=token["access_token"],
        expires=timezone.now() + datetime.timedelta(seconds=token["expires_in"]),
        refresh_token=token["refresh_token"],
    )


def refresh_token(token: SpotifyAccessToken) -> SpotifyAccessToken:
    response = requests.post(
        url="https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
        },
        headers=get_token_request_headers(),
        timeout=10,
    )
    token_json = response.json()
    token.access_token = token_json["access_token"]
    token.expires = timezone.now() + datetime.timedelta(seconds=token_json["expires_in"])
    token.save(update_fields=["access_token", "expires"])
    return token


class AuthCallbackHandler(BaseHTTPRequestHandler):
    def write_response(self, encoding, content: str):
        encoded = content.encode(encoding, "surrogateescape")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-type", f"text/html; charset={encoding}")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    # pylint: disable=invalid-name
    def do_GET(self):
        parsed_url = urlparse(self.path)
        qs = parse_qs(parsed_url.query)
        if "code" in qs:
            auth_code = qs["code"][0]
            response = requests.post(
                url="https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "redirect_uri": REDIRECT_URI,
                },
                headers=get_token_request_headers(),
                timeout=10,
            )
            save_access_token(response.json())
        self.write_response(encoding=sys.getfilesystemencoding(), content="You may close this browser tab.")


def authorize():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    url = (
        f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code"
        f"&redirect_uri={REDIRECT_URI}&scope=user-library-read"
    )
    webbrowser.open_new_tab(url)
    with HTTPServer((REDIRECT_HOST, REDIRECT_PORT), AuthCallbackHandler) as httpd:
        httpd.timeout = 60
        httpd.handle_request()


def get_spotify_response(url: str, response_type: Type[AbstractSpotifyResponse[ABR]]) -> AbstractSpotifyResponse[ABR]:
    response = spotify_get(url=url)
    if response.status_code >= 400:
        time.sleep(5)
        return get_spotify_response(url, response_type)

    return response_type.from_dict(response.json())


def spotify_get(url: str) -> requests.Response:
    try:
        access_token = SpotifyAccessToken.objects.latest("expires")
        if access_token.is_expired:
            access_token = refresh_token(access_token)
        return requests.get(
            url=url,
            headers={"Authorization": f"Bearer {access_token.access_token}"},
            timeout=10,
        )
    except SpotifyAccessToken.DoesNotExist:
        authorize()
        return spotify_get(url)
