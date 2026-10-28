
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser

from .models import Event, Photo
from .serializers import EventSerializer, PhotoSerializer


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [AllowAny]
        elif self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]


class PhotoViewSet(viewsets.ModelViewSet):
    queryset = Photo.objects.select_related("event").all()
    serializer_class = PhotoSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        event_id = self.request.query_params.get("event")

        if event_id:
            queryset = queryset.filter(event_id=event_id)

        return queryset

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [AllowAny]
        elif self.action == "create":
            permission_classes = [IsAuthenticated]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]
