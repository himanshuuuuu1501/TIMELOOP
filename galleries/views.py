
from rest_framework import viewsets
from .models import Event, Photo
from .serializers import EventSerializer, PhotoSerializer


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


class PhotoViewSet(viewsets.ModelViewSet):
    queryset = Photo.objects.select_related("event").all()
    serializer_class = PhotoSerializer
