from django.db import models
from django.utils import timezone


class SpotifyAccessToken(models.Model):
    access_token = models.CharField(max_length=300)
    expires = models.DateTimeField()
    refresh_token = models.CharField(max_length=300)

    @property
    def is_expired(self):
        return self.expires < timezone.now()
