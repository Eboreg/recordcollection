import re
from typing import Any, Iterable, TypeVar

import requests

from recordcollection.models import Genre


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
        "IDM",
        "MPB",
        "OPM",
        "RKT",
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
        old_genres = [g.lower() for g in Genre.objects.values_list("name", flat=True)]
        new_genres = []
        for line in response.text.splitlines():
            if line.lower() not in old_genres:
                if line.lower() in special_cases_dict:
                    new_genres.append(Genre(name=special_cases_dict[line.lower()]))
                else:
                    new_genres.append(Genre(name=capitalize(line)))
        Genre.objects.bulk_create(new_genres)
