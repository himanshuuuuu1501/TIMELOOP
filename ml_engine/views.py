import itertools

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

from galleries.models import Photo, SavedPhotoMatch


SIMILARITY_THRESHOLD = 0.30


class PersonSearchView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .face_search import extract_face_embeddings, compare_embeddings

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
                with photo.image.open("rb") as image_file:
                    with Image.open(image_file) as stored_image:
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
        from .face_search import extract_face_embeddings, compare_embeddings

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
            from ml_engine.clip_search import create_text_embedding, cosine_similarity
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

        # Detect an explicitly requested exact number of people.
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
            r"\b" + number_pattern + r"\s+(?:people|persons|person|men|women|guests|individuals)\b",
            query.lower()
        )

        requested_people_count = None
        if count_match:
            raw_count = count_match.group(1)
            requested_people_count = (
                int(raw_count) if raw_count.isdigit() else number_words[raw_count]
            )

        # Keep the existing flexible ranking for ordinary natural-language searches.
        query_lower = query.lower()
        interaction_terms = [
            "kiss", "kissing", "hug", "hugging", "embrace",
            "cry", "crying", "laugh", "laughing", "dance",
            "dancing", "smile", "smiling", "garland",
            "vidaai", "farewell"
        ]
        is_interaction_search = any(
            term in query_lower for term in interaction_terms
        )

        if requested_people_count is not None:
            # If an exact count is requested, do not allow CLIP-only or
            # unindexed photos through. Gemini count confidence must be >= 0.75.
            filtered_results = [
                item for item in results
                if (
                    item["scene_indexed"]
                    and item["visible_people_count"] == requested_people_count
                    and item["people_count_confidence"] >= 0.75
                )
            ]

            # If the query also names an action, require that action to appear
            # in Gemini's saved action/description/scene text.
            person_words = {
                "people", "person", "persons", "man", "men", "woman",
                "women", "guest", "guests", "individual", "individuals"
            }
            action_words = set(re.findall(r"[a-z]+", query_lower))
            action_words -= person_words
            action_words -= set(number_words)
            action_words -= {
                "a", "an", "the", "is", "are", "was", "were", "in",
                "on", "at", "of", "to", "with", "and", "someone",
                "somebody", "who", "that", "exactly"
            }
            action_aliases = {
                "hug": {"hug", "hugging", "embrace", "embracing"},
                "hugging": {"hug", "hugging", "embrace", "embracing"},
                "kiss": {"kiss", "kissing"},
                "kissing": {"kiss", "kissing"},
                "stand": {"stand", "standing"},
                "standing": {"stand", "standing"},
                "sit": {"sit", "sitting", "seated"},
                "sitting": {"sit", "sitting", "seated"},
                "dance": {"dance", "dancing"},
                "dancing": {"dance", "dancing"},
                "smile": {"smile", "smiling"},
                "smiling": {"smile", "smiling"},
                "laugh": {"laugh", "laughing", "laughter"},
                "laughing": {"laugh", "laughing", "laughter"},
                "cry": {"cry", "crying", "weeping", "sobbing"},
                "crying": {"cry", "crying", "weeping", "sobbing"},
                "pose": {"pose", "posing"},
                "posing": {"pose", "posing"},
            }

            requested_action_terms = set()
            for word in action_words:
                requested_action_terms.update(action_aliases.get(word, {word}))

            if requested_action_terms:
                strict_matches = []
                for item in filtered_results:
                    analysis = scene_analyses.get(item["photo_id"])
                    if not analysis:
                        continue

                    action_text_parts = [analysis.description or "", analysis.search_text or ""]
                    actions_data = analysis.actions if isinstance(analysis.actions, list) else []
                    for action_item in actions_data:
                        if isinstance(action_item, dict):
                            action_text_parts.extend([
                                str(action_item.get("action", "")),
                                str(action_item.get("description", "")),
                                str(action_item.get("details", "")),
                            ])
                        elif isinstance(action_item, str):
                            action_text_parts.append(action_item)

                    action_text = " ".join(action_text_parts).lower()
                    action_text_words = set(re.findall(r"[a-z]+", action_text))
                    if requested_action_terms.intersection(action_text_words):
                        strict_matches.append(item)

                filtered_results = strict_matches

        elif is_interaction_search:
            filtered_results = [
                item for item in results
                if (
                    item["scene_score"] >= 0.30
                    or item["similarity"] >= 0.235
                )
            ]
        else:
            filtered_results = [
                item for item in results
                if (
                    item["scene_score"] >= 0.30
                    or item["similarity"] >= 0.27
                )
            ]

        return Response({
                "query": query,
                "event_id": event_id,
                "photos_checked": len(results),
                "gemini_analyses_available": len(scene_analyses),
                "ranking_method": "Gemini scene descriptions + CLIP + YOLO",
                "exact_people_count_filter": requested_people_count,
                "results": filtered_results[:5],
                "matches_found": len(filtered_results[:5]),
                "total_candidates": len(filtered_results),
            })


class PersonMomentSearchView(APIView):
    """
    Find photos containing every selected reference identity.
    Face identities are matched to distinct detected faces in each candidate.
    Available scene analysis is then used to rank action relevance.
    """

    from .face_search import extract_face_embeddings, compare_embeddings

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    ACTION_GROUPS = {
        "hugging": {"hug", "hugs", "hugging", "embrace", "embracing", "cuddle", "cuddling"},
        "kissing": {"kiss", "kisses", "kissing", "peck"},
        "dancing": {"dance", "dances", "dancing"},
        "crying": {"cry", "cries", "crying", "weeping", "sobbing", "tears"},
        "laughing": {"laugh", "laughs", "laughing", "laughter", "giggle", "giggling"},
        "smiling": {"smile", "smiles", "smiling", "grinning"},
        "standing": {"stand", "stands", "standing", "stood"},
        "sitting": {"sit", "sits", "sitting", "seated"},
        "posing": {"pose", "poses", "posing", "photographed", "photograph"},
        "walking": {"walk", "walks", "walking"},
        "talking": {"talk", "talks", "talking", "chat", "chatting", "conversation"},
        "feeding": {"feed", "feeds", "feeding"},
        "waving": {"wave", "waves", "waving"},
    }

    def post(self, request):
        query = request.data.get("query", "").strip()
        event_id = request.data.get("event_id")
        try:
            requested_count = int(request.data.get("person_count", 0))
        except (TypeError, ValueError):
            requested_count = 0

        if requested_count == 0:
            # Backward compatibility with the original two-person frontend.
            requested_count = 2 if (
                request.FILES.get("person_one") and request.FILES.get("person_two")
            ) else 0

        if requested_count < 2 or requested_count > 4:
            return Response(
                {"error": "Choose between 2 and 4 people."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not query:
            return Response(
                {"error": "Describe the moment you want to find."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        references = []
        for index in range(1, requested_count + 1):
            uploaded = request.FILES.get(f"person_{index}")
            if uploaded is None and index == 1:
                uploaded = request.FILES.get("person_one")
            if uploaded is None and index == 2:
                uploaded = request.FILES.get("person_two")

            if uploaded is None:
                return Response(
                    {"error": f"Please upload a reference photo for Person {index}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                image = Image.open(uploaded).convert("RGB")
            except (UnidentifiedImageError, OSError):
                return Response(
                    {"error": f"Person {index}'s reference file is not a valid image."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            detected = extract_face_embeddings(image)
            if not detected:
                return Response(
                    {"error": f"No face was detected in Person {index}'s reference photo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            references.append(detected[0])

        photos = Photo.objects.select_related("event").all()
        if event_id:
            try:
                photos = photos.filter(event_id=int(event_id))
            except (TypeError, ValueError):
                return Response(
                    {"error": "event_id must be a valid integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        analyses = {
            item.photo_id: item
            for item in PhotoSceneAnalysis.objects.filter(photo__in=photos)
        }

        # Expand common action phrases into their related forms.
        query_tokens = set(re.findall(r"[a-z]+", query.lower()))
        matched_action_groups = [
            (group_name, vocab)
            for group_name, vocab in self.ACTION_GROUPS.items()
            if query_tokens.intersection(vocab)
        ]
        requested_action_vocab = set().union(
            *(vocab for _, vocab in matched_action_groups)
        ) if matched_action_groups else set()

        results = []
        checked = 0

        for photo in photos.iterator():
            checked += 1
            try:
                with photo.image.open("rb") as image_file:
                    with Image.open(image_file) as stored:
                        candidate_faces = extract_face_embeddings(
                            stored.convert("RGB")
                        )
            except (OSError, ValueError, UnidentifiedImageError):
                continue

            # Each requested identity must map to a DIFFERENT face in the photo.
            # This prevents one detected face from satisfying multiple people.
            if len(candidate_faces) < requested_count:
                continue

            best_assignment = None
            best_key = None
            for assignment in itertools.permutations(candidate_faces, requested_count):
                scores = [
                    compare_embeddings(reference, candidate_face)
                    for reference, candidate_face in zip(references, assignment)
                ]
                key = (min(scores), sum(scores) / len(scores))
                if best_key is None or key > best_key:
                    best_key = key
                    best_assignment = scores

            if not best_assignment or any(
                score < SIMILARITY_THRESHOLD for score in best_assignment
            ):
                continue

            analysis = analyses.get(photo.id)
            scene_parts = []
            if analysis:
                scene_parts.extend([
                    analysis.description or "",
                    analysis.search_text or "",
                ])
                if isinstance(analysis.actions, list):
                    for action in analysis.actions:
                        if isinstance(action, dict):
                            scene_parts.extend([
                                str(action.get("action", "")),
                                str(action.get("description", "")),
                                str(action.get("details", "")),
                            ])
                        elif isinstance(action, str):
                            scene_parts.append(action)

            scene_text = " ".join(scene_parts).lower()
            scene_tokens = set(re.findall(r"[a-z]+", scene_text))

            # Score action relevance by semantic action-family evidence.
            matched_groups = []
            for group_name, vocabulary in matched_action_groups:
                if scene_tokens.intersection(vocabulary):
                    matched_groups.append(group_name)

            action_score = (
                len(matched_groups) / len(matched_action_groups)
                if matched_action_groups else 0.0
            )
            action_verified = bool(matched_groups) if matched_action_groups else False
            identity_min = min(best_assignment)
            identity_average = sum(best_assignment) / len(best_assignment)

            # Identity is the hard requirement. Action evidence affects ranking,
            # but unindexed photos remain visible and are labelled unverified.
            ranking_score = identity_min * 0.75 + identity_average * 0.25
            if matched_action_groups:
                ranking_score += action_score * 0.18

            results.append({
                "photo_id": photo.id,
                "event_id": photo.event_id,
                "event_name": photo.event.name,
                "filename": photo.original_filename,
                "image_url": request.build_absolute_uri(photo.image.url),
                "people_count_required": requested_count,
                "people_found": requested_count,
                "person_similarities": [round(score, 4) for score in best_assignment],
                "minimum_person_similarity": round(identity_min, 4),
                "all_people_verified": True,
                "scene_indexed": analysis is not None,
                "action_verified": action_verified,
                "matched_actions": matched_groups,
                "action_score": round(action_score, 3),
                "scene_description": (analysis.description[:300] if analysis else ""),
                "ranking_score": round(ranking_score, 4),
                "verification_note": (
                    "All selected people matched distinct faces. Scene analysis supports "
                    "the requested action."
                    if action_verified else
                    "All selected people matched distinct faces. The requested action "
                    "could not be verified from available scene analysis."
                ),
            })

        results.sort(
            key=lambda item: (
                item["action_verified"],
                item["action_score"],
                item["ranking_score"],
            ),
            reverse=True,
        )

        return Response({
            "query": query,
            "event_id": event_id,
            "people_required": requested_count,
            "photos_checked": checked,
            "gemini_analyses_available": len(analyses),
            "candidate_photos_with_all_people": len(results),
            "results": results[:30],
            "message": (
                f"Every result contains all {requested_count} selected people. "
                "Action relevance is ranked using available scene descriptions."
            ),
        })
