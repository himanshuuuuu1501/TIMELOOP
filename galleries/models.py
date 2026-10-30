
from django.conf import settings
from django.db import models
import uuid


class Event(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_date = models.DateField(null=True, blank=True)
    join_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Photo(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="events/%Y/%m/")
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_filename or 'Photo'} - {self.event.name}"


class SavedPhotoMatch(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_photo_matches",
    )
    photo = models.ForeignKey(
        Photo,
        on_delete=models.CASCADE,
        related_name="saved_matches",
    )
    similarity = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-similarity", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "photo"],
                name="unique_saved_photo_match_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.photo}"
