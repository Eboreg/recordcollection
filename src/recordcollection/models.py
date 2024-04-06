from typing import Self

from django.contrib import admin
from django.db import models
from django.db.models.functions import Lower


class AbstractItem(models.Model):
    musicbrainz_id = models.CharField(max_length=200, null=True, default=None, blank=True)
    spotify_id = models.CharField(max_length=200, null=True, default=None, blank=True)
    discogs_id = models.IntegerField(null=True, default=None, blank=True)

    class Meta:
        abstract = True


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)

    class Meta:
        ordering = [Lower("name")]

    def __str__(self):
        return self.name


class Track(AbstractItem):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=500)
    track_number = models.SmallIntegerField(null=True, default=None, verbose_name="track #", blank=True)
    disc_number = models.SmallIntegerField(null=True, default=None, verbose_name="disc #", blank=True)
    year = models.SmallIntegerField(null=True, default=None, blank=True)
    album = models.ForeignKey("Album", on_delete=models.CASCADE, null=True, default=None, related_name="tracks")
    artists = models.ManyToManyField("Artist", related_name="tracks", through="TrackArtist")
    duration = models.DurationField(null=True, default=None, blank=True)
    file_path = models.CharField(max_length=1000, null=True, default=None, blank=True)
    genres = models.ManyToManyField("Genre", related_name="tracks", blank=True)

    track_artists: models.Manager["TrackArtist"]
    album_id: int | None

    class Meta:
        ordering = [Lower("title")]

    def __str__(self):
        return self.title

    @classmethod
    def prefetched(cls) -> models.QuerySet[Self]:
        return cls.objects.prefetch_related("track_artists__artist", "genres")

    @admin.display(description="artist")
    def artist_string(self) -> str:
        result = ""
        track_artists = list(self.track_artists.all())

        for idx, track_artist in enumerate(track_artists):
            result += track_artist.artist.name
            if len(track_artists) > idx + 1:
                join_phrase = track_artist.join_phrase or "/"
                result += f" {join_phrase} "

        return result


class Album(AbstractItem):
    class Medium(models.TextChoices):
        CD = "CD", "CD"
        VINYL = "VIN"
        FILE = "FIL"
        STREAMING = "STR"

    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=500)
    year = models.SmallIntegerField(null=True, default=None, blank=True)
    musicbrainz_group_id = models.CharField(max_length=200, null=True, default=None, blank=True)
    artists = models.ManyToManyField("Artist", related_name="albums", through="AlbumArtist")
    is_compilation = models.BooleanField(default=False, verbose_name="V/A")
    medium = models.CharField(max_length=3, choices=Medium.choices, null=True, default=None, blank=True)
    genres = models.ManyToManyField("Genre", related_name="albums", blank=True)

    album_artists: models.Manager["AlbumArtist"]

    tracks: models.Manager["Track"]

    class Meta:
        ordering = [Lower("title")]

    def __str__(self):
        return self.title

    @classmethod
    def prefetched(cls) -> models.QuerySet[Self]:
        return cls.objects.prefetch_related(
            models.Prefetch("tracks", queryset=Track.prefetched().order_by("disc_number", "track_number")),
            "album_artists__artist",
            "artists",
            "genres",
        )

    @admin.display(description="artist")
    def artist_string(self) -> str | None:
        if self.is_compilation:
            return None

        result = ""
        album_artists = list(self.album_artists.all())

        for idx, album_artist in enumerate(album_artists):
            result += album_artist.artist.name
            if len(album_artists) > idx + 1:
                join_phrase = album_artist.join_phrase or "/"
                result += f" {join_phrase} "

        return result

    def update_from_musicbrainz(self) -> "Album":
        from musicbrainz.functions import get_best_musicbrainz_album_match

        match = get_best_musicbrainz_album_match(album=self)
        if match and match.ratio >= 0.8:
            return match.release.update_album(album=self)
        if self.musicbrainz_id is None:
            self.musicbrainz_id = ""
            self.save(update_fields=["musicbrainz_id"])
        return self


class Artist(AbstractItem):
    name = models.CharField(max_length=500)

    class Meta:
        ordering = [Lower("name")]
        constraints = [
            # MariaDB doesn't support unique constraints on expressions:
            models.UniqueConstraint(Lower("name"), name="unique_artist_name_ci"),
            models.UniqueConstraint("name", name="unique_artist_name"),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def iupdate_or_create(cls, name: str, **kwargs):
        artist = cls.objects.filter(name__iexact=name).first()
        if artist:
            if any(getattr(artist, key) != value for key, value in kwargs.items()):
                for key, value in kwargs.items():
                    setattr(artist, key, value)
                artist.save(update_fields=kwargs.keys())
            return artist
        return cls.objects.create(name=name, **kwargs)


class AbstractArtistCredit(models.Model):
    artist = models.ForeignKey("Artist", on_delete=models.CASCADE, related_name="+")
    position = models.SmallIntegerField(default=0)
    join_phrase = models.CharField(max_length=100, default="/", blank=True)

    class Meta:
        ordering = ["position"]
        abstract = True


class TrackArtist(AbstractArtistCredit):
    track = models.ForeignKey("Track", on_delete=models.CASCADE, related_name="track_artists")

    class Meta(AbstractArtistCredit.Meta):
        constraints = [
            models.UniqueConstraint(fields=["track", "artist"], name="unique_track_artist"),
        ]


class AlbumArtist(AbstractArtistCredit):
    album = models.ForeignKey("Album", on_delete=models.CASCADE, related_name="album_artists")

    class Meta(AbstractArtistCredit.Meta):
        constraints = [
            models.UniqueConstraint(fields=["album", "artist"], name="unique_album_artist"),
        ]
