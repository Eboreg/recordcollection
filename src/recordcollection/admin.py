import functools
import operator
import re

from django.contrib import admin
from django.db.models import CharField, Count, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Concat, Lower
from django.db.models.query import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import smart_split, unescape_string_literal

from recordcollection.admin_filters import (
    AlbumCountFilter,
    AlbumGenreFilter,
    HasMusicBrainzIDFilter,
    TrackDurationFilter,
    TrackGenreFilter,
)
from recordcollection.models import (
    Album,
    AlbumArtist,
    Artist,
    Genre,
    Track,
    TrackArtist,
)


def artist_link_list(artists: list[Artist]):
    if artists:
        return format_html(
            "<br>".join([
                format_html(
                    '<a href="{}">{}</a>',
                    reverse("admin:recordcollection_artist_change", args=(artist.pk,)),
                    artist.name,
                )
                for artist in artists
            ])
        )
    return None


# INLINES #####################################################################

class AlbumArtistInline(admin.TabularInline):
    autocomplete_fields = ("artist",)
    extra = 0
    model = AlbumArtist
    show_change_link = True
    verbose_name = "artist"
    verbose_name_plural = "artists"


class AlbumTrackInline(admin.TabularInline):
    extra = 0
    fields = ("artist_string", "title", "disc_number", "track_number", "duration", "year")
    model = Track
    readonly_fields = ("artist_string",)
    show_change_link = True

    def get_queryset(self, request: HttpRequest) -> QuerySet[Track]:
        return (
            super().get_queryset(request)
            .order_by("disc_number", "track_number")
            .prefetch_related("track_artists__artist")
        )


class ArtistAlbumInline(admin.TabularInline):
    autocomplete_fields = ("album",)
    extra = 0
    fields = ("album",)
    model = AlbumArtist
    show_change_link = True
    verbose_name = "album"
    verbose_name_plural = "albums"


class TrackArtistInline(admin.TabularInline):
    autocomplete_fields = ["artist"]
    extra = 0
    model = TrackArtist
    show_change_link = True
    verbose_name = "artist"
    verbose_name_plural = "artists"


# MODEL ADMINS ################################################################

class AbstractBaseAdmin(admin.ModelAdmin):
    readonly_fields = ("musicbrainz_id", "spotify_id", "discogs_id")
    save_on_top = True

    class Media:
        css = {"all": ["admin.css"]}


@admin.register(Album)
class AlbumAdmin(AbstractBaseAdmin):
    fields = [
        ("title", "year", "medium", "is_compilation"),
        ("musicbrainz_id", "musicbrainz_group_id", "spotify_id", "discogs_id"),
        "genres",
    ]
    filter_horizontal = ("genres",)
    list_display = [
        "title_display",
        "artist_list",
        "year",
        "track_count",
        "medium",
        "genre_list",
        "is_compilation",
        "play_count",
    ]
    list_filter = [
        "is_compilation",
        "medium",
        HasMusicBrainzIDFilter,
        ("genres", AlbumGenreFilter),
    ]
    readonly_fields = ("musicbrainz_id", "musicbrainz_group_id", "spotify_id", "discogs_id")
    search_fields = ["title", "artists__name", "year", "genres__name"]

    def get_inlines(self, request, obj):
        if obj and obj.is_compilation:
            return [AlbumTrackInline]
        return [AlbumArtistInline, AlbumTrackInline]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Album]:
        return (
            super().get_queryset(request)
            .prefetch_related("album_artists__artist", "genres")
            .annotate(
                track_count=Count("tracks", distinct=True),
                artist_order=Subquery(
                    AlbumArtist.objects.filter(album=OuterRef("pk")).values(name=Lower("artist__name"))[:1],
                ),
                play_count=Sum("tracks__play_count"),
            )
            .order_by("artist_order", "year")
        )

    @admin.display(ordering=Concat("is_compilation", "artist_order", output_field=CharField()), description="artists")
    def artist_list(self, obj: Album):
        return artist_link_list([a.artist for a in obj.album_artists.all()])

    @admin.display(description="genres", ordering="genre_order")
    def genre_list(self, obj: Album):
        return format_html(
            "<br>".join(f"<span style=\"white-space:nowrap\">{genre.name}</span>" for genre in obj.genres.all())
        )

    @admin.display(ordering="play_count")
    def play_count(self, obj):
        return obj.play_count

    @admin.display(ordering=Lower("title"), description="title")
    def title_display(self, obj: Album):
        return obj.title

    @admin.display(description="# tracks", ordering="track_count")
    def track_count(self, obj):
        if obj.track_count > 0:
            return format_html(
                '<a href="{}?album__id__exact={}&o=4.5">{}</a>',
                reverse("admin:recordcollection_track_changelist"),
                obj.pk,
                obj.track_count,
            )
        return obj.track_count


@admin.register(Artist)
class ArtistAdmin(AbstractBaseAdmin):
    fields = ("name", ("musicbrainz_id", "spotify_id", "discogs_id"))
    inlines = [ArtistAlbumInline]
    list_display = ["name", "album_count", "track_count", "play_count"]
    list_filter = [AlbumCountFilter, HasMusicBrainzIDFilter]
    search_fields = ["name"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Artist]:
        return super().get_queryset(request).annotate(
            album_count=Count("albums", distinct=True),
            track_count=Count("tracks", distinct=True),
            play_count=Sum("albums__tracks__play_count", distinct=True),
        )

    @admin.display(ordering="album_count", description="# albums")
    def album_count(self, obj):
        if obj.album_count > 0:
            return format_html(
                '<a href="{}?artists__id__exact={}">{}</a>',
                reverse("admin:recordcollection_album_changelist"),
                obj.pk,
                obj.album_count,
            )
        return obj.album_count

    @admin.display(ordering="play_count")
    def play_count(self, obj):
        return obj.play_count

    @admin.display(ordering="track_count", description="# tracks")
    def track_count(self, obj):
        if obj.track_count > 0:
            return format_html(
                '<a href="{}?artists__id__exact={}">{}</a>',
                reverse("admin:recordcollection_track_changelist"),
                obj.pk,
                obj.track_count,
            )
        return obj.track_count


@admin.register(Track)
class TrackAdmin(AbstractBaseAdmin):
    autocomplete_fields = ("album",)
    fields = [
        ("title", "album"),
        ("disc_number", "track_number"),
        ("year", "duration"),
        "genres",
        ("file_path", "musicbrainz_id", "spotify_id", "discogs_id"),
    ]
    filter_horizontal = ("genres",)
    inlines = [TrackArtistInline]
    list_display = [
        "title",
        "artist_list",
        "album_link",
        "year",
        "genre_list",
        "rounded_duration",
        "play_count",
        "album_medium",
    ]
    list_filter = [
        HasMusicBrainzIDFilter,
        TrackDurationFilter,
        ("genres", TrackGenreFilter),
    ]
    search_fields = [
        "album__artists__name",
        "album__title",
        "album__year",
        "artists__name",
        "genres__name",
        "title",
        "year",
    ]
    search_help_text = "Prefix search with \"title:\", \"album:\", or \"artist:\" to only search specific fields."

    def get_queryset(self, request: HttpRequest) -> QuerySet[Track]:
        return (
            super().get_queryset(request)
            .select_related("album")
            .prefetch_related("track_artists__artist", "genres")
            .annotate(
                artist_order=Subquery(
                    TrackArtist.objects.filter(track=OuterRef("pk")).values(name=Lower("artist__name"))[:1],
                ),
                genre_order=Subquery(
                    Genre.objects.filter(tracks=OuterRef("pk")).values(iname=Lower("name"))[:1],
                )
            )
        )

    def get_search_results(self, request, queryset, search_term):
        lookups: list[str] = []
        regex: re.Pattern | None = None

        if search_term.lower().startswith("title:"):
            regex = re.compile(r"^title: *(.*)$", flags=re.IGNORECASE)
            lookups = ["title__icontains"]
        elif search_term.lower().startswith("album:"):
            regex = re.compile(r"^album: *(.*)$", flags=re.IGNORECASE)
            lookups = ["album__title__icontains"]
        elif search_term.lower().startswith("artist:"):
            regex = re.compile(r"^artist: *(.*)$", flags=re.IGNORECASE)
            lookups = ["album__artists__name__icontains", "artists__name__icontains"]

        if regex and lookups:
            term_queries = []
            search_term = regex.sub(r"\1", search_term)
            for bit in smart_split(search_term):
                if bit.startswith(('"', "'")) and bit[0] == bit[-1]:
                    bit = unescape_string_literal(bit)
                or_queries = functools.reduce(operator.or_, [Q(**{lookup: bit}) for lookup in lookups], Q())
                term_queries.append(or_queries)
            queryset = queryset.filter(functools.reduce(operator.and_, term_queries, Q()))
            return queryset, False

        return super().get_search_results(request, queryset, search_term)

    @admin.display(ordering="album__title", description="album")
    def album_link(self, obj: Track):
        if obj.album:
            return format_html(
                '<a href="{}">{}</a>',
                reverse(
                    "admin:recordcollection_album_change",
                    args=(obj.album.id,),
                    current_app=self.admin_site.name,
                ),
                obj.album,
            )
        return None

    @admin.display(ordering="album__medium", description="medium")
    def album_medium(self, obj: Track):
        return obj.album.get_medium_display() if obj.album else None

    @admin.display(ordering="artist_order", description="artists")
    def artist_list(self, obj: Track):
        return artist_link_list([a.artist for a in obj.track_artists.all()])

    @admin.display(description="genres", ordering="genre_order")
    def genre_list(self, obj: Track):
        return format_html("<br>".join(genre.name for genre in obj.genres.all()))

    @admin.display(ordering="duration", description="duration")
    def rounded_duration(self, obj: Track):
        if obj.duration:
            total_seconds = obj.duration.total_seconds()
            minutes = int(total_seconds / 60)
            seconds = round(total_seconds % 60)
            return f"{minutes}:{seconds:02}"
        return None
