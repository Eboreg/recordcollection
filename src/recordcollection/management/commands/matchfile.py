import functools
import operator
import re
from typing import Iterator, Sequence

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q

from recordcollection.models import Album, Artist, Track
from recordcollection.utils import chunked


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser):
        parser.add_argument("filename")
        parser.add_argument("--mode", "-m", choices=("track", "album", "artist"), default="track")
        parser.add_argument("--wholewords", "-w", action="store_true")

    def get_matches(self, mode: str, rows: list[str], wholewords: bool = False) -> Iterator[tuple[str, list[str]]]:
        qs = self.get_queryset(mode)
        for chunk in chunked(rows, 100):
            chunk_filter = self.get_filter(mode, chunk)
            chunk_objects = list(qs.filter(chunk_filter))
            for row in chunk:
                if wholewords:
                    patt = re.compile(rf"(?<!\w){row}(?!\w)", flags=re.IGNORECASE)
                else:
                    patt = re.compile(row, flags=re.IGNORECASE)
                row_strings = []
                for obj in chunk_objects:
                    if self.object_matches(obj, patt):
                        row_strings.append(self.object_to_string(obj))
                yield row, row_strings

    def object_matches(self, obj: Track | Artist | Album, patt: re.Pattern) -> bool:
        if isinstance(obj, Album):
            return bool(patt.search(obj.title))
        if isinstance(obj, Artist):
            return bool(patt.search(obj.name))
        return bool(patt.search(obj.title))

    def object_to_string(self, obj: Track | Artist | Album) -> str:
        if isinstance(obj, Album):
            artist = obj.artist_string()
            output = f"[{obj.id}] "
            output += f"{artist} - {obj.title}" if artist else obj.title
            return output
        if isinstance(obj, Artist):
            return f"[{obj.pk}] {obj.name}"
        artist = obj.artist_string()
        output = f"[{obj.id}] "
        output += f"{artist} - {obj.title}" if artist else obj.title
        if obj.album:
            output += f" ({obj.album.title})"
        return output

    def get_filter(self, mode: str, chunk: Sequence[str]):
        if mode == "album":
            return functools.reduce(operator.or_, [Q(title__icontains=row) for row in chunk], Q())
        if mode == "artist":
            return functools.reduce(operator.or_, [Q(name__icontains=row) for row in chunk], Q())
        return functools.reduce(operator.or_, [Q(title__icontains=row) for row in chunk], Q())

    def get_queryset(self, mode: str):
        if mode == "album":
            return Album.objects.prefetch_related("album_artists__artist")
        if mode == "artist":
            return Artist.objects.all()
        return Track.objects.select_related("album").prefetch_related("track_artists__artist")

    def handle(self, *args, **options):
        rows = []
        with open(options["filename"], "rt", encoding="utf8") as f:
            rows = [row.strip() for row in f.readlines()]

        for row, results in self.get_matches(options["mode"], rows, options["wholewords"]):
            if results:
                self.stdout.write(row + "\n-----------------------------")
                for result in results:
                    self.stdout.write(result)
                self.stdout.write("")
