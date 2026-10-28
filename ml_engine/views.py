
from PIL import Image, UnidentifiedImageError
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from galleries.models import Photo, SavedPhotoMatch
from .face_search import extract_face_embeddings, compare_embeddings


SIMILARITY_THRESHOLD = 0.30


class PersonSearchView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reference_file = request.FILES.get("reference_image")

        if not reference_file:
            return Response(
                {"error": "Upload a reference_image file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reference_image = Image.open(reference_file).convert("RGB")
        except (UnidentifiedImageError, OSError):
            return Response(
                {"error": "The uploaded file is not a valid image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference_embeddings = extract_face_embeddings(reference_image)

        if not reference_embeddings:
            return Response(
                {"error": "No face was detected in the reference photo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference_embedding = reference_embeddings[0]

        # Optionally limit the search to one wedding event.
        event_id = request.data.get("event_id")
        photos = Photo.objects.select_related("event").all()

        if event_id:
            try:
                event_id = int(event_id)
            except (TypeError, ValueError):
                return Response(
                    {"error": "event_id must be a valid integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            photos = photos.filter(event_id=event_id)

        results = []

        for photo in photos:
            try:
                with Image.open(photo.image.path) as stored_image:
                    image = stored_image.convert("RGB")
                    candidate_embeddings = extract_face_embeddings(image)
            except (OSError, ValueError):
                continue

            if not candidate_embeddings:
                continue

            best_score = max(
                compare_embeddings(reference_embedding, candidate)
                for candidate in candidate_embeddings
            )

            if best_score < SIMILARITY_THRESHOLD:
                continue

            # Persist the match for the authenticated user.
            saved_match, created = SavedPhotoMatch.objects.update_or_create(
                user=request.user,
                photo=photo,
                defaults={"similarity": round(best_score, 4)},
            )

            results.append({
                "photo_id": photo.id,
                "event_id": photo.event_id,
                "event_name": photo.event.name,
                "filename": photo.original_filename,
                "image_url": request.build_absolute_uri(photo.image.url),
                "similarity": round(best_score, 4),
                "saved": True,
            })

        results.sort(
            key=lambda item: item["similarity"],
            reverse=True,
        )

        return Response({
            "message": "Person search completed and matches saved.",
            "event_id": event_id,
            "photos_checked": photos.count(),
            "matches_saved": len(results),
            "results": results[:50],
        })
