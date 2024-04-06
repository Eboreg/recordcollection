from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Q
from django.db.models.functions import Lower

from recordcollection.models import Genre


class HasMusicBrainzIDFilter(admin.SimpleListFilter):
    title = "has MBID"
    parameter_name = "has_mbid"

    def lookups(self, request, model_admin):
        return [
            ("0", "No"),
            ("1", "Yes"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "0":
            return queryset.filter(Q(musicbrainz_id=None) | Q(musicbrainz_id=""))
        if self.value() == "1":
            return queryset.exclude(Q(musicbrainz_id=None) | Q(musicbrainz_id=""))
        return queryset


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


class AlbumGenreFilter(admin.RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        qs = (
            Genre.objects
            .annotate(album_count=Count("albums"))
            .filter(album_count__gt=0)
            .order_by("-album_count", Lower("name"))
        )
        return [(genre.pk, genre.name) for genre in qs]


class TrackGenreFilter(admin.RelatedFieldListFilter):
    def field_choices(self, field, request, model_admin):
        qs = (
            Genre.objects
            .annotate(track_count=Count("tracks"))
            .filter(track_count__gt=0)
            .order_by("-track_count", Lower("name"))
        )
        return [(genre.pk, genre.name) for genre in qs]


class TrackDurationFilter(admin.SimpleListFilter):
    title = "duration"
    parameter_name = "duration"

    def lookups(self, request, model_admin):
        return [
            ("any", "Any duration"),
            ("1minus", "< 1 min"),
            ("2minus", "< 2 min"),
            ("3minus", "< 3 min"),
            ("5minus", "< 5 min"),
            ("5plus", ">= 5 min"),
            ("10plus", ">= 10 min"),
            ("15plus", ">= 15 min"),
            ("20plus", ">= 20 min"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "any":
            return queryset.exclude(duration=None)
        if self.value() == "1minus":
            return queryset.filter(duration__lt=timedelta(minutes=1))
        if self.value() == "2minus":
            return queryset.filter(duration__lt=timedelta(minutes=2))
        if self.value() == "3minus":
            return queryset.filter(duration__lt=timedelta(minutes=3))
        if self.value() == "5minus":
            return queryset.filter(duration__lt=timedelta(minutes=5))
        if self.value() == "5plus":
            return queryset.filter(duration__gte=timedelta(minutes=5))
        if self.value() == "10plus":
            return queryset.filter(duration__gte=timedelta(minutes=10))
        if self.value() == "15plus":
            return queryset.filter(duration__gte=timedelta(minutes=15))
        if self.value() == "20plus":
            return queryset.filter(duration__gte=timedelta(minutes=20))
        return queryset
