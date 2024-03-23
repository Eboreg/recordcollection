import datetime
import hashlib
import re
from pathlib import Path

from django.db import transaction
from django.db.models import Q
from tinytag import TinyTag

from recordcollection.models import (
    Album, AlbumArtist, Artist, Genre, Track, TrackArtist,
)
from recordcollection.utils import group_and_count, int_or_none


def file_to_track_title(file: Path) -> str:
    return re.sub(r"^(?:\d+ (?:- )?)?(.*)$", r"\1", file.stem).strip()


def file_to_tinytag(file: Path) -> TinyTag:
    tag = TinyTag.get(str(file.absolute()))
    if tag.album is not None:
        tag.album = tag.album.strip()
    if tag.albumartist is not None:
        tag.albumartist = tag.albumartist.strip()
    if tag.artist is not None:
        tag.artist = tag.artist.strip()
    if tag.title is not None:
        tag.title = tag.title.strip()
    return tag


def tinytag_to_track(file: Path, tag: TinyTag, file_idx: int, album_id: int | None = None) -> Track:
    file_path = str(file.absolute())
    year_match = re.match(r"^(\d{4}).*$", tag.year) if tag.year else None
    disc_number = int_or_none(tag.disc) or 1
    track_number = int_or_none(tag.track) or file_idx + 1
    year = int(year_match.group(1)) if year_match else None
    duration = datetime.timedelta(seconds=round(tag.duration)) if tag.duration else None
    title = tag.title or file_to_track_title(file)

    track = Track.objects.filter(Q(file_path=None) | Q(file_path=file_path)).update_or_create(
        album_id=album_id,
        disc_number=disc_number,
        track_number=track_number,
        defaults={
            "file_path": file_path,
            "title": title,
            "year": year,
            "duration": duration,
        }
    )[0]
    artist_name = tag.artist or tag.albumartist
    if artist_name:
        artist = Artist.iupdate_or_create(name=artist_name)
        TrackArtist.objects.update_or_create(track=track, artist=artist)
    if tag.genre:
        genre = Genre.objects.filter(name__iexact=tag.genre).first()
        if genre:
            track.genres.add(genre)

    return track


@transaction.atomic
def scan_audio_files(
    files: list[Path],
    existing_file_paths: list[str],
    is_compilation: bool = False,
    total: bool = False,
):
    albums: set[Album] = set()
    album_artists = []

    for file_idx, file in enumerate(sorted(files, key=lambda f: f.name)):
        if not total and str(file.absolute()) in existing_file_paths:
            continue

        tag = file_to_tinytag(file)
        artist_name = tag.artist or tag.albumartist
        album_id: int | None = None

        if tag.albumartist:
            album_artists.append(tag.albumartist)

        if (artist_name or is_compilation) and tag.album:
            assert isinstance(tag.album, str)
            album: Album | None = None

            track_albums = [album for album in albums if album.title == tag.album]
            if track_albums:
                album = track_albums[0]

            if album is None:
                track_album_qs = Album.objects.filter(title__iexact=tag.album, medium=Album.Medium.FILE)
                if is_compilation:
                    track_album_qs = track_album_qs.filter(is_compilation=True)
                else:
                    artist_filter = Q()
                    if tag.albumartist:
                        artist_filter = Q(artists__name__iexact=tag.albumartist)
                    if tag.artist:
                        artist_filter = artist_filter | Q(artists__name__iexact=tag.artist)
                    track_album_qs = track_album_qs.filter(artist_filter)
                album = track_album_qs.first()

            if album is not None:
                if album.is_compilation != is_compilation:
                    album.is_compilation = is_compilation
                    album.save(update_fields=["is_compilation"])
            else:
                album = Album.objects.create(
                    title=tag.album,
                    is_compilation=is_compilation,
                    medium=Album.Medium.FILE,
                )

            albums.add(album)
            album_id = album.id

        tinytag_to_track(file=file, tag=tag, album_id=album_id, file_idx=file_idx)

    for album in albums:
        tracks = list(album.tracks.all())
        track_years = {track.year for track in tracks if track.year}
        track_genres = list(Genre.objects.filter(tracks__in=tracks))

        if not is_compilation:
            grouped_album_artists = group_and_count(album_artists)
            if grouped_album_artists:
                top_album_artist = max(grouped_album_artists.items(), key=lambda item: item[1])[0]
                artist = Artist.iupdate_or_create(name=top_album_artist)
                AlbumArtist.objects.update_or_create(album=album, artist=artist)
            else:
                grouped_artists = group_and_count([artist for track in tracks for artist in track.artists.all()])
                if grouped_artists:
                    top_artist = max(grouped_artists.items(), key=lambda item: item[1])[0]
                    AlbumArtist.objects.update_or_create(album=album, artist=top_artist)

        if len(track_years) == 1:
            album.year = list(track_years)[0]
            album.save(update_fields=["year"])

        if track_genres:
            album.genres.add(*track_genres)

        print(repr(album))


def scan_directory_recursive(
    directory: Path,
    exceptions: list[Path],
    existing_file_paths: list[str],
    is_compilation: bool = False,
    total: bool = False,
) -> set[str]:
    audio_files: list[Path] = []
    is_compilation = is_compilation or directory.name.lower() == "various artists"
    file_paths: set[str] = set(existing_file_paths)
    print(directory.absolute())

    for file in directory.iterdir():
        if any(file.is_relative_to(e) for e in exceptions):
            continue
        if file.is_file() and TinyTag.is_supported(file.name):
            audio_files.append(file)
            file_paths.add(str(file.absolute()))
        elif file.is_dir():
            file_paths.update(
                scan_directory_recursive(
                    directory=file,
                    exceptions=exceptions,
                    existing_file_paths=existing_file_paths,
                    is_compilation=is_compilation,
                    total=total,
                )
            )

    scan_audio_files(
        files=audio_files,
        existing_file_paths=existing_file_paths,
        is_compilation=is_compilation,
        total=total,
    )

    return file_paths


def get_file_hash(file: Path) -> str:
    with file.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256")
    return digest.hexdigest()
