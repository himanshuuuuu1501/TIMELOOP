
from django.db import models
from galleries.models import Photo


class PhotoEmbedding(models.Model):
    """
    Stores a reusable CLIP embedding for each photo.
    Each photo needs to be indexed only once unless it changes.
    """

    photo = models.OneToOneField(
        Photo,
        on_delete=models.CASCADE,
        related_name="clip_embedding",
    )

    embedding = models.JSONField(
        help_text="CLIP image embedding stored as a list of numbers."
    )

    model_name = models.CharField(
        max_length=100,
        default="clip-vit-base-patch32",
    )

    indexed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["photo_id"]

    def __str__(self):
        return f"CLIP embedding for photo {self.photo_id}"

class PhotoYOLOIndex(models.Model):
    photo = models.OneToOneField(
        "galleries.Photo",
        on_delete=models.CASCADE,
        related_name="yolo_index"
    )

    detections = models.JSONField(
        default=list,
        help_text="Detected objects, confidence scores and bounding boxes."
    )

    model_name = models.CharField(
        max_length=100,
        default="yolo26n"
    )

    indexed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"YOLO index for photo {self.photo_id}"



class PhotoSceneAnalysis(models.Model):
    photo = models.OneToOneField(
        "galleries.Photo",
        on_delete=models.CASCADE,
        related_name="scene_analysis"
    )

    description = models.TextField(blank=True)

    people = models.JSONField(default=list)
    actions = models.JSONField(default=list)
    emotions = models.JSONField(default=list)
    interactions = models.JSONField(default=list)
    setting = models.JSONField(default=dict)

    search_text = models.TextField(blank=True)

    model_name = models.CharField(
        max_length=100,
        default="gemini-3.8-flash"
    )

    indexed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["photo_id"]

    def __str__(self):
        return f"Scene analysis for photo {self.photo_id}"
