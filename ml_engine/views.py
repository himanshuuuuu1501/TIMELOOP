
from PIL import Image, UnidentifiedImageError
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ml_engine.models import (
    PhotoEmbedding,
    PhotoYOLOIndex,
    PhotoSceneAnalysis,
)
from ml_engine.clip_search import create_text_embedding, cosine_similarity

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


from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from galleries.models import SavedPhotoMatch


class SavedMatchesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        matches = (
            SavedPhotoMatch.objects
            .filter(user=request.user)
            .select_related("photo", "photo__event")
            .order_by("-similarity", "-created_at")
        )

        results = []

        for match in matches:
            photo = match.photo

            results.append({
                "id": match.id,
                "photo_id": photo.id,
                "event_id": photo.event_id,
                "event_name": photo.event.name,
                "filename": photo.original_filename,
                "image_url": request.build_absolute_uri(photo.image.url),
                "similarity": round(match.similarity, 4),
                "created_at": match.created_at.isoformat(),
            })

        return Response({
            "count": len(results),
            "results": results,
        })



import re


class SceneSearchView(APIView):
    permission_classes = [IsAuthenticated]

    # Maps natural-language object names to YOLO's COCO class names.
    OBJECT_ALIASES = {
        "car": ["car"],
        "cars": ["car"],
        "automobile": ["car"],
        "vehicle": ["car", "truck", "bus", "motorcycle"],
        "vehicles": ["car", "truck", "bus", "motorcycle"],
        "truck": ["truck"],
        "trucks": ["truck"],
        "bus": ["bus"],
        "buses": ["bus"],
        "motorcycle": ["motorcycle"],
        "motorcycles": ["motorcycle"],
        "bike": ["motorcycle"],
        "bikes": ["motorcycle"],
        "person": ["person"],
        "people": ["person"],
        "man": ["person"],
        "woman": ["person"],
        "men": ["person"],
        "women": ["person"],
        "human": ["person"],
        "cat": ["cat"],
        "cats": ["cat"],
        "dog": ["dog"],
        "dogs": ["dog"],
        "bird": ["bird"],
        "birds": ["bird"],
        "horse": ["horse"],
        "horses": ["horse"],
        "airplane": ["airplane"],
        "airplanes": ["airplane"],
        "plane": ["airplane"],
        "planes": ["airplane"],
        "boat": ["boat"],
        "boats": ["boat"],
        "chair": ["chair"],
        "chairs": ["chair"],
        "backpack": ["backpack"],
        "suitcase": ["suitcase"],
        "suitcases": ["suitcase"],
        "bottle": ["bottle"],
        "bottles": ["bottle"],
        "cup": ["cup"],
        "cups": ["cup"],
        "clock": ["clock"],
        "clocks": ["clock"],
        "kite": ["kite"],
        "kites": ["kite"],
        "bird": ["bird"],
        "birds": ["bird"],
        "bear": ["bear"],
        "bears": ["bear"],
        "elephant": ["elephant"],
        "elephants": ["elephant"],
        "zebra": ["zebra"],
        "zebras": ["zebra"],
        "giraffe": ["giraffe"],
        "giraffes": ["giraffe"],
        "umbrella": ["umbrella"],
        "umbrellas": ["umbrella"],
        "handbag": ["handbag"],
        "handbags": ["handbag"],
        "laptop": ["laptop"],
        "laptops": ["laptop"],
        "phone": ["cell phone"],
        "phones": ["cell phone"],
        "cellphone": ["cell phone"],
        "cellphones": ["cell phone"],
        "mobile": ["cell phone"],
        "mobiles": ["cell phone"],
        "tv": ["tv"],
        "television": ["tv"],
        "televisions": ["tv"],
        "refrigerator": ["refrigerator"],
        "refrigerators": ["refrigerator"],
        "pizza": ["pizza"],
        "pizzas": ["pizza"],
        "cake": ["cake"],
        "cakes": ["cake"],
        "sandwich": ["sandwich"],
        "sandwiches": ["sandwich"],
        "apple": ["apple"],
        "apples": ["apple"],
        "banana": ["banana"],
        "bananas": ["banana"],
        "orange": ["orange"],
        "oranges": ["orange"],
        "broccoli": ["broccoli"],
        "carrot": ["carrot"],
        "carrots": ["carrot"],
        "flower": ["potted plant"],
        "flowers": ["potted plant"],
        "plant": ["potted plant"],
        "plants": ["potted plant"],
        "vase": ["vase"],
        "vases": ["vase"],
    }


    def post(self, request):
        query = request.data.get("query", "").strip()
        event_id = request.data.get("event_id")

        if not query:
            return Response(
                {"error": "Please provide a search query."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(query) > 500:
            return Response(
                {"error": "Search query must be 500 characters or fewer."},
                status=status.HTTP_400_BAD_REQUEST
            )

        photos = Photo.objects.select_related("event").filter(
            id__in=PhotoEmbedding.objects.values_list(
                "photo_id", flat=True
            )
        )

        if event_id:
            try:
                event_id = int(event_id)
            except (TypeError, ValueError):
                return Response(
                    {"error": "event_id must be a valid integer."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            photos = photos.filter(event_id=event_id)

        try:
            text_embedding = create_text_embedding(query)
        except Exception as error:
            return Response(
                {"error": f"Unable to process search query: {str(error)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Extract meaningful search terms.
        stop_words = {
            "a", "an", "the", "is", "are", "was", "were",
            "in", "on", "at", "of", "to", "with", "and",
            "during", "for", "from", "by", "someone", "somebody"
        }

        query_words = set(re.findall(r"[a-z]+", query.lower()))
        search_terms = query_words - stop_words

        # Expand common expressions into related visual descriptions.
        synonyms = {
            "crying": {"tears", "weeping", "sobbing", "emotional"},
            "cries": {"tears", "weeping", "sobbing"},
            "cried": {"tears", "weeping", "sobbing"},
            "bride": {"bridal", "wedding", "woman"},
            "groom": {"groom", "wedding", "man"},
            "vidaai": {"farewell", "departure", "goodbye"},
            "hugging": {"embracing", "embrace", "arms"},
            "hug": {"embracing", "embrace"},
            "dancing": {"dance", "celebrating"},
            "laughing": {"laughter", "smiling", "joy"},
            "smiling": {"smile", "happy", "joy"},
            "garlands": {"garland", "flowers", "ceremony"},
            "garland": {"flowers", "ceremony"},
        }

        expanded_terms = set(search_terms)

        for word in search_terms:
            expanded_terms.update(synonyms.get(word, set()))

        # Load Gemini analyses for the candidate photos.
        scene_analyses = {
            item.photo_id: item
            for item in PhotoSceneAnalysis.objects.filter(
                photo__in=photos
            )
        }

        # Load YOLO detections.
        yolo_indexes = {
            item.photo_id: item.detections
            for item in PhotoYOLOIndex.objects.filter(
                photo__in=photos
            )
        }

        embeddings = PhotoEmbedding.objects.filter(
            photo__in=photos
        ).select_related("photo", "photo__event")

        results = []

        for stored_embedding in embeddings.iterator(chunk_size=200):
            photo = stored_embedding.photo

            try:
                clip_score = cosine_similarity(
                    text_embedding,
                    stored_embedding.embedding
                )
            except (TypeError, ValueError):
                continue

            # GEMINI SCENE MATCHING
            analysis = scene_analyses.get(photo.id)

            scene_score = 0.0
            matched_terms = []

            if analysis:
                scene_text = analysis.search_text.lower()
                scene_words = set(
                    re.findall(r"[a-z]+", scene_text)
                )

                matched_terms = sorted(
                    expanded_terms.intersection(scene_words)
                )

                if expanded_terms:
                    scene_score = (
                        len(matched_terms) / len(expanded_terms)
                    )

            # YOLO OBJECT MATCHING
            detections = yolo_indexes.get(photo.id, [])
            matched_objects = []

            requested_objects = set()

            for word in query_words:
                requested_objects.update(
                    self.OBJECT_ALIASES.get(word, [])
                )

            for detection in detections:
                object_name = detection.get("object")
                confidence = float(
                    detection.get("confidence", 0)
                )

                if (
                    object_name in requested_objects
                    and confidence >= 0.25
                ):
                    matched_objects.append({
                        "object": object_name,
                        "confidence": round(confidence, 4)
                    })

            yolo_boost = 0.03 if matched_objects else 0.0

            # Read Gemini's estimated total visible-person count.
            visible_people_count = None
            people_count_confidence = 0.0

            if analysis:
                setting = analysis.setting if isinstance(analysis.setting, dict) else {}
                people_count_data = setting.get("people_count", {})

                if isinstance(people_count_data, dict):
                    visible_people_count = people_count_data.get("visible_count")
                    try:
                        people_count_confidence = float(
                            people_count_data.get("confidence", 0.0)
                        )
                    except (TypeError, ValueError):
                        people_count_confidence = 0.0

            # COMBINED RANKING
            scene_boost = scene_score * 0.15

            hybrid_score = (
                clip_score + scene_boost + yolo_boost
            )

            results.append({
                "photo_id": photo.id,
                "event_id": photo.event_id,
                "event_name": photo.event.name,
                "filename": photo.original_filename,
                "image_url": request.build_absolute_uri(
                    photo.image.url
                ),
                "similarity": round(clip_score, 4),
                "scene_score": round(scene_score, 4),
                "scene_indexed": analysis is not None,
                "visible_people_count": visible_people_count,
                "people_count_confidence": round(people_count_confidence, 3),
                "matched_scene_terms": matched_terms,
                "yolo_matches": matched_objects,
                "yolo_boost": yolo_boost,
                "scene_boost": round(scene_boost, 4),
                "hybrid_score": round(hybrid_score, 4),
            })

        results.sort(
            key=lambda item: item["hybrid_score"],
            reverse=True
        )

        # Detect an explicitly requested number of people.
        number_words = {
            "one": 1, "two": 2, "three": 3, "four": 4,
            "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
            "thirteen": 13, "fourteen": 14, "fifteen": 15,
            "sixteen": 16, "seventeen": 17, "eighteen": 18,
            "nineteen": 19, "twenty": 20,
        }
        number_pattern = r"(\d{1,2}|" + "|".join(number_words) + r")"
        count_match = re.search(
            r"\b" + number_pattern
            + r"\s+(?:people|persons|person|men|women|guests|individuals)\b",
            query.lower(),
        )

        requested_people_count = None
        if count_match:
            raw_count = count_match.group(1)
            requested_people_count = (
                int(raw_count) if raw_count.isdigit() else number_words[raw_count]
            )

        # Build a small action vocabulary. Gemini's fields can vary between
        # "action", "description", "people_count", and "people_involved".
        action_aliases = {
            "hug": {"hug", "hugging", "embrace", "embracing"},
            "hugging": {"hug", "hugging", "embrace", "embracing"},
            "embrace": {"hug", "hugging", "embrace", "embracing"},
            "kiss": {"kiss", "kissing"},
            "kissing": {"kiss", "kissing"},
            "cry": {"cry", "crying", "weeping", "sobbing", "tears"},
            "crying": {"cry", "crying", "weeping", "sobbing", "tears"},
            "dance": {"dance", "dancing"},
            "dancing": {"dance", "dancing"},
            "stand": {"stand", "standing"},
            "standing": {"stand", "standing"},
            "sit": {"sit", "sitting", "seated"},
            "sitting": {"sit", "sitting", "seated"},
            "laugh": {"laugh", "laughing", "laughter"},
            "laughing": {"laugh", "laughing", "laughter"},
            "smile": {"smile", "smiling"},
            "smiling": {"smile", "smiling"},
            "pose": {"pose", "posing"},
            "posing": {"pose", "posing"},
        }

        ignored_words = {
            "a", "an", "the", "is", "are", "was", "were", "in", "on",
            "at", "of", "to", "with", "and", "during", "for", "from",
            "by", "someone", "somebody", "people", "person", "persons",
            "men", "women", "guests", "individuals", "exactly",
        }
        query_tokens = set(re.findall(r"[a-z]+", query.lower()))
        requested_action_tokens = query_tokens - ignored_words
        requested_action_tokens -= set(number_words.keys())
        requested_action_tokens -= {str(n) for n in range(1, 21)}

        expanded_action_tokens = set()
        for token in requested_action_tokens:
            expanded_action_tokens.update(action_aliases.get(token, {token}))

        def gemini_action_matches(photo_id):
            analysis = scene_analyses.get(photo_id)
            if not analysis:
                return False

            text_parts = [
                analysis.description or "",
                analysis.search_text or "",
            ]
            actions_data = analysis.actions if isinstance(analysis.actions, list) else []
            for action_item in actions_data:
                if isinstance(action_item, dict):
                    text_parts.extend([
                        str(action_item.get("action", "")),
                        str(action_item.get("description", "")),
                        str(action_item.get("details", "")),
                    ])
                elif isinstance(action_item, str):
                    text_parts.append(action_item)

            scene_tokens = set(
                re.findall(r"[a-z]+", " ".join(text_parts).lower())
            )
            return bool(expanded_action_tokens.intersection(scene_tokens))

        query_lower = query.lower()
        interaction_terms = {
            "kiss", "kissing", "hug", "hugging", "embrace",
            "cry", "crying", "laugh", "laughing", "dance",
            "dancing", "smile", "smiling", "garland", "vidaai",
            "farewell", "posing", "pose", "standing", "sitting",
        }
        is_interaction_search = bool(
            interaction_terms.intersection(query_tokens)
        )

        if requested_people_count is not None:
            # First choice: photos with a confident Gemini count AND matching
            # action evidence. Never treat YOLO boxes as an exact people count.
            verified_matches = []
            for item in results:
                count_is_verified = (
                    item["scene_indexed"]
                    and item["visible_people_count"] == requested_people_count
                    and item["people_count_confidence"] >= 0.75
                )
                action_is_verified = (
                    not expanded_action_tokens
                    or gemini_action_matches(item["photo_id"])
                )
                if count_is_verified and action_is_verified:
                    item["people_count_verified"] = True
                    item["count_note"] = "People count is supported by scene analysis."
                    verified_matches.append(item)

            if verified_matches:
                filtered_results = verified_matches
            else:
                # Important: do not return zero just because most of the gallery
                # has not received Gemini analysis yet. Return visual candidates,
                # clearly marked as NOT count-verified.
                filtered_results = [
                    item for item in results
                    if item["similarity"] >= 0.20
                    and (
                        not is_interaction_search
                        or item["scene_score"] >= 0.15
                        or item["similarity"] >= 0.22
                    )
                ]
                for item in filtered_results:
                    item["people_count_verified"] = False
                    item["count_note"] = (
                        f"Requested count: {requested_people_count}. "
                        "This photo has not been verified for that exact count."
                    )
        else:
            # Prefer Gemini-supported scene matches. If no indexed scene matches
            # strongly enough, use CLIP's best visual candidates as a fallback
            # rather than claiming that no moment exists.
            if is_interaction_search:
                filtered_results = [
                    item for item in results
                    if item["scene_score"] >= 0.20
                    or item["similarity"] >= 0.235
                ]
            else:
                filtered_results = [
                    item for item in results
                    if item["scene_score"] >= 0.20
                    or item["similarity"] >= 0.25
                ]

            if not filtered_results:
                fallback_floor = 0.18
                filtered_results = [
                    item for item in results
                    if item["similarity"] >= fallback_floor
                ]
                for item in filtered_results:
                    item["visual_similarity_only"] = True

        # Keep the strongest results first. Count-verified results are ranked
        # by the same hybrid score as all other results.
        filtered_results.sort(
            key=lambda item: (
                item.get("people_count_verified", False),
                item["hybrid_score"],
            ),
            reverse=True,
        )

        return Response({
            "query": query,
            "event_id": event_id,
            "photos_checked": len(results),
            "gemini_analyses_available": len(scene_analyses),
            "ranking_method": "Gemini scene evidence + CLIP visual retrieval + YOLO object evidence",
            "exact_people_count_filter": requested_people_count,
            "count_filter_mode": (
                "verified_only_when_available_with_unverified_visual_fallback"
                if requested_people_count is not None
                else None
            ),
            "results": filtered_results[:5],
            "matches_found": len(filtered_results[:5]),
            "total_candidates": len(filtered_results),
        })
