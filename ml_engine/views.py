
from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from galleries.models import Photo
from .face_search import extract_face_embeddings, compare_embeddings


class PersonSearchView(APIView):
    parser_classes = [MultiPartParser, FormParser]

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

        print("API reference image size:", reference_image.size)
        print("API detected embeddings:", len(reference_embeddings))

        if not reference_embeddings:
            return Response(
                {"error": "No face was detected in the reference photo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference_embedding = reference_embeddings[0]
        photos = Photo.objects.select_related("event").all()
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

            results.append({
                "photo_id": photo.id,
                "event_id": photo.event_id,
                "event_name": photo.event.name,
                "filename": photo.original_filename,
                "image_url": request.build_absolute_uri(photo.image.url),
                "similarity": round(best_score, 4),
            })

        results.sort(key=lambda item: item["similarity"], reverse=True)

        return Response({
            "message": "Person search completed.",
            "photos_checked": photos.count(),
            "results": results[:50],
        })
