
from rest_framework import serializers
from .models import Event, Photo


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ("id", "name", "description", "event_date", "created_at")
        read_only_fields = ("id", "created_at")


class PhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Photo
        fields = "__all__"
