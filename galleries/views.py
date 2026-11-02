from django.core import signing
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response

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
        invitation_token = request.data.get("token", "")
        event = Event.objects.filter(join_token=invitation_token).first()
        if event is None:
            return Response(
                {"error": "This event invitation is invalid or expired."},
                status=status.HTTP_404_NOT_FOUND,
            )

        upload_token = signing.dumps(
            {"event_id": event.id},
            salt="timeloop-guest-upload",
        )
        return Response({
            "joined": True,
            "upload_token": upload_token,
            "event": {
                "id": event.id,
                "name": event.name,
                "description": event.description,
                "event_date": event.event_date,
            },
            "message": f"You joined {event.name}. You can now upload photos.",
        })

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def invite(self, request, pk=None):
        event = self.get_object()
        return Response({
            "event_id": event.id,
            "event_name": event.name,
            "token": str(event.join_token),
        })


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

    def _save_and_process(self, serializer):
        photo = serializer.save()
        # Upload success is never rolled back because an AI provider is unavailable.
        # The request waits for the three model jobs, so a successful response means
        # processing has finished (or reports which model failed in the server log).
        from ml_engine.photo_processing import process_uploaded_photo
        result = process_uploaded_photo(photo)
        self._ai_processing_result = result
        return photo

    def perform_create(self, serializer):
        event = serializer.validated_data.get("event")
        user = self.request.user
        is_admin = user.is_authenticated and user.is_staff

        if is_admin:
            self._save_and_process(serializer)
            return

        upload_token = self.request.data.get("upload_token", "")
        try:
            token_data = signing.loads(
                upload_token,
                salt="timeloop-guest-upload",
                max_age=7 * 24 * 60 * 60,
            )
        except signing.BadSignature:
            raise PermissionDenied(
                "Invalid or expired event upload permission. Please scan the event QR code again."
            )

        if event is None or str(token_data.get("event_id")) != str(event.id):
            raise PermissionDenied(
                "This invitation does not belong to the selected event."
            )

        self._save_and_process(serializer)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        if hasattr(self, "_ai_processing_result"):
            response.data["ai_processing"] = self._ai_processing_result
        return response
