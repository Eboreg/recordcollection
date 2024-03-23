from django.contrib import admin
from django.db.models import CharField, Count, OuterRef, Subquery
from django.db.models.functions import Concat, Lower
from django.db.models.query import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html

from recordcollection.models import (
    Album, AlbumArtist, Artist, Genre, Track, TrackArtist,
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


class AlbumTrackInline(admin.TabularInline):
    model = Track
    extra = 0
    fields = ("title", "disc_number", "track_number", "duration", "year")
    show_change_link = True

    def get_queryset(self, request: HttpRequest) -> QuerySet[Track]:
        return super().get_queryset(request).order_by("disc_number", "track_number")


class AlbumArtistInline(admin.TabularInline):
    model = AlbumArtist
    extra = 0
    autocomplete_fields = ("artist",)
    verbose_name = "artist"
    verbose_name_plural = "artists"
    show_change_link = True


class ArtistAlbumInline(admin.TabularInline):
    model = AlbumArtist
    extra = 0
    verbose_name = "album"
    verbose_name_plural = "albums"
    fields = ("album",)
    autocomplete_fields = ("album",)
    show_change_link = True


class AlbumCountFilter(admin.SimpleListFilter):
    title = "album count"
    parameter_name = "album_count"

    def lookups(self, request, model_admin):
        return [
            ("0", "0"),
            ("1", "1+"),
            ("5", "5+"),
            ("10", "10+"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "0":
            return queryset.filter(album_count=0)
        if self.value() == "1":
            return queryset.filter(album_count__gte=1)
        if self.value() == "5":
            return queryset.filter(album_count__gte=5)
        if self.value() == "10":
            return queryset.filter(album_count__gte=10)
        return queryset


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    inlines = [ArtistAlbumInline]
    list_display = ["name", "album_count", "track_count"]
    list_filter = [AlbumCountFilter]
    fields = ("name", "musicbrainz_id", "spotify_id", "discogs_id",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Artist]:
        return super().get_queryset(request).annotate(
            album_count=Count("albums", distinct=True),
            track_count=Count("tracks", distinct=True),
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


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "artist_list",
        "year",
        "track_count",
        "medium",
        "genre_list",
        "is_compilation",
    ]
    search_fields = ["title", "artists__name", "year", "genres__name"]
    inlines = [AlbumArtistInline, AlbumTrackInline]
    list_filter = [
        "is_compilation",
        "medium",
        ("genres", admin.RelatedOnlyFieldListFilter),
    ]
    filter_horizontal = ("genres",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Album]:
        return (
            super().get_queryset(request)
            .prefetch_related("album_artists__artist", "genres")
            .annotate(
                track_count=Count("tracks"),
                artist_order=Subquery(
                    AlbumArtist.objects.filter(album=OuterRef("pk")).values(name=Lower("artist__name"))[:1],
                ),
            )
            .order_by("artist_order", "year")
        )

    @admin.display(ordering=Concat("is_compilation", "artist_order", output_field=CharField()), description="artists")
    def artist_list(self, obj: Album):
        return artist_link_list([a.artist for a in obj.album_artists.all()])

    @admin.display(description="genres", ordering="genre_order")
    def genre_list(self, obj: Album):
        return format_html("<br>".join(genre.name for genre in obj.genres.all()))

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


class TrackArtistInline(admin.TabularInline):
    model = TrackArtist
    extra = 0
    autocomplete_fields = ["artist"]
    verbose_name = "artist"
    verbose_name_plural = "artists"
    show_change_link = True


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "artist_list",
        "album_link",
        "disc_number",
        "track_number",
        "year",
        "genre_list",
        "rounded_duration",
    ]
    search_fields = [
        "title",
        "artists__name",
        "year",
        "album__title",
        "album__artists__name",
        "album__year",
        "genres__name",
    ]
    autocomplete_fields = ("album",)
    inlines = [TrackArtistInline]
    fields = [
        "title",
        "album",
        ("disc_number", "track_number"),
        ("year", "duration"),
        "genres",
        ("file_path", "file_hash"),
        ("musicbrainz_id", "spotify_id", "discogs_id"),
    ]
    list_filter = [
        ("genres", admin.RelatedOnlyFieldListFilter),
    ]

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
