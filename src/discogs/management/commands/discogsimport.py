from django.core.management.base import BaseCommand

from discogs.functions import get_release, get_user_release_response
from recordcollection.utils import import_musicbrainz_genres


class Command(BaseCommand):
    def handle(self, *args, **options):
        page = 1
        pages: int | None = None
        total: int | None = None
        idx = 0

        import_musicbrainz_genres()

        while pages is None or page <= pages:
            response = get_user_release_response(page)
            total = response.pagination.items
            pages = response.pagination.pages
            for user_release in response.releases:
                release = get_release(user_release.basic_information.id)
                album = release.to_album()
                if total:
                    print(f"[{idx + 1}/{total}] {album}")
                else:
                    print(album)
                idx += 1
            page += 1
