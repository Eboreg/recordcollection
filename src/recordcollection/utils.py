import datetime
import os
import re
from typing import Any, Iterable, TypeVar

import dotenv
import requests

from recordcollection import __version__
from recordcollection.models import Artist, Genre


_T = TypeVar("_T")


def group_and_count(seq: Iterable[_T]) -> dict[_T, int]:
    result: dict[_T, int] = {}
    for item in seq:
        if item in result:
            result[item] += 1
        else:
            result[item] = 1
    return result


def int_or_none(value: Any | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def capitalize(value: str) -> str:
    """
    Translation: "Capitalize every letter that is the first character in the
    string, or is preceeded by a non-letter"
    """
    return re.sub(r"((^\w)|(?<=\W)(\w))", lambda m: m.group(1).upper(), value)


def import_musicbrainz_genres():
    response = requests.get("https://musicbrainz.org/ws/2/genre/all?fmt=txt", timeout=10)
    special_cases = [
        "AOR",
        "ASMR",
        "EAI",
        "EBM",
        "EDM",
        "FM Synthesis",
        "Hi-NRG",
        "IDM",
        "MPB",
        "OPM",
        "RKT",
        "Trap EDM",
        "UK Drill",
        "UK Funky",
        "UK Garage",
        "UK Hardcore",
        "UK Jackin",
        "UK Street Soul",
        "UK82",
    ]
    special_cases_dict = {g.lower(): g for g in special_cases}

    if response.status_code == 200:
        old_genres = list(Genre.objects.all())
        new_genres = []
        updated_genres = []

        for line in response.text.splitlines():
            genre_name: str
            if line.lower() in special_cases_dict:
                genre_name = special_cases_dict[line.lower()]
            else:
                genre_name = capitalize(line)

            matches = [g for g in old_genres if g.name.lower() == line.lower()]
            if matches:
                old_genre = matches[0]
                if old_genre.name != genre_name:
                    old_genre.name = genre_name
                    updated_genres.append(old_genre)
            else:
                new_genres.append(Genre(name=genre_name))

        if new_genres:
            Genre.objects.bulk_create(new_genres)
        if updated_genres:
            Genre.objects.bulk_update(updated_genres, fields=["name"])


def delete_orphan_artists():
    Artist.objects.filter(albums=None, tracks=None).delete()


def get_user_agent() -> str:
    return f"recordcollection/{__version__} +robert@huseli.us"


def get_env_datetime(key: str) -> datetime.datetime | None:
    timestamp = os.environ.get(key, None)
    if timestamp:
        return datetime.datetime.fromtimestamp(float(timestamp), tz=datetime.timezone.utc)
    return None


def set_env_datetime(key: str, value: datetime.datetime | None = None):
    value = value or datetime.datetime.now(tz=datetime.timezone.utc)
    dotenv.set_key(
        dotenv_path=dotenv.find_dotenv(),
        key_to_set=key,
        value_to_set=str(value.timestamp()),
    )
