
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser

from .models import Event, Photo
from .serializers import EventSerializer, PhotoSerializer


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "join"]:
            permission_classes = [AllowAny]
        elif self.action in ["create", "update", "partial_update", "destroy", "invite"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def join(self, request):
        token = request.data.get("token", "")
        event = Event.objects.filter(join_token=token).first()
        if event is None:
            return Response({"error": "This event invitation is invalid or expired."}, status=status.HTTP_404_NOT_FOUND)

        joined = request.session.get("joined_event_ids", [])
        event_id = str(event.id)
        if event_id not in joined:
            joined.append(event_id)
        request.session["joined_event_ids"] = joined
        request.session.modified = True

        return Response({
            "joined": True,
            "event": {
                "id": event.id,
                "name": event.name,
                "description": event.description,
                "event_date": event.event_date,
            },
            "message": f"You joined {event.name}.",
        })

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def invite(self, request, pk=None):
        event = self.get_object()
        return Response({"event_id": event.id, "event_name": event.name, "token": str(event.join_token)})


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
        if self.action in ["list", "retrieve", "create"]:
            permission_classes = [AllowAny]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        event = serializer.validated_data.get("event")
        joined_event_ids = self.request.session.get("joined_event_ids", [])
        is_admin = self.request.user.is_authenticated and self.request.user.is_staff
        if not is_admin and str(event.id) not in joined_event_ids:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Scan this event's QR code before uploading photos.")
        serializer.save()
