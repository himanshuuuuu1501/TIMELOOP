"""Automatic AI processing for newly uploaded TIMELOOP photos.

Reads images through Django's storage API, so Cloudinary works without .path.
CLIP, Gemini and YOLO run concurrently. Failures in one model do not prevent
successful results from the other models or prevent the photo upload itself.
"""

import io
import json
import logging
import mimetypes
import os
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
from PIL import Image, ImageOps
from dotenv import load_dotenv
from django.conf import settings

from galleries.models import Photo
from ml_engine.models import PhotoEmbedding, PhotoSceneAnalysis, PhotoYOLOIndex
from ml_engine.clip_search import create_image_embedding

logger = logging.getLogger(__name__)

GEMINI_MODEL_NAME = "gemini-3.8-flash"
YOLO_MODEL_NAME = "yolo26n.pt"

GEMINI_PROMPT = """
You are analysing a photograph for TIMELOOP, an intelligent visual memory search system.
Return ONLY valid JSON with these fields:
{
  "description": "Detailed natural-language description of the photograph.",
  "people": [],
  "actions": [],
  "emotions": [],
  "interactions": [],
  "total_people": {
    "visible_count": null,
    "confidence": 0.0,
    "counting_notes": ""
  },
  "setting": {
    "location": "",
    "event": "",
    "time": "",
    "details": []
  }
}
Focus on specific moments, actions, interactions, expressions and emotions.
Only describe observable evidence. Do not invent identities, relationships or emotions.
Do not assume the event is a wedding without visual evidence. Do not identify real people.
Distinguish people standing close together from actively interacting.
Be detailed enough to support natural-language searches. Return valid JSON only.
"""


def _read_photo(photo):
    if not photo.image:
        raise ValueError("Photo has no image file.")
    with photo.image.open("rb") as source:
        image_bytes = source.read()
    image = Image.open(io.BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    return image_bytes, image


def _process_clip(photo, image):
    embedding = create_image_embedding(image)
    PhotoEmbedding.objects.update_or_create(
        photo=photo,
        defaults={
            "embedding": embedding,
            "model_name": "openai/clip-vit-base-patch32",
        },
    )
    return True


@lru_cache(maxsize=1)
def _get_yolo_model():
    from ultralytics import YOLO
    return YOLO(YOLO_MODEL_NAME)


def _process_yolo(photo, image):
    model = _get_yolo_model()
    results = model.predict(
        source=np.asarray(image),
        conf=0.10,
        verbose=False,
    )

    detections = []
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            coordinates = box.xyxy[0].cpu().tolist()
            detections.append({
                "object": model.names[class_id],
                "confidence": round(confidence, 4),
                "bbox": [round(value, 2) for value in coordinates],
            })

    PhotoYOLOIndex.objects.update_or_create(
        photo=photo,
        defaults={"detections": detections, "model_name": "yolo26n"},
    )
    return True


@lru_cache(maxsize=1)
def _get_gemini_client():
    load_dotenv(os.path.join(settings.BASE_DIR, ".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from the local .env file.")
    from google import genai
    return genai.Client(api_key=api_key)


def _process_gemini(photo, image_bytes):
    from google.genai import types

    client = _get_gemini_client()
    mime_type, _ = mimetypes.guess_type(photo.image.name or "")
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"
    last_error = None

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[
                    GEMINI_PROMPT,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            if not response.text:
                raise ValueError("Gemini returned an empty response.")
            data = json.loads(response.text)
            break
        except Exception as error:
            last_error = error
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    else:
        raise last_error or RuntimeError("Gemini analysis failed.")

    description = data.get("description", "")
    people = data.get("people", [])
    actions = data.get("actions", [])
    emotions = data.get("emotions", [])
    interactions = data.get("interactions", [])
    setting = data.get("setting", {})

    if not isinstance(description, str):
        raise ValueError("Gemini returned an invalid description.")
    for field_name, field_value in (
        ("people", people),
        ("actions", actions),
        ("emotions", emotions),
        ("interactions", interactions),
    ):
        if not isinstance(field_value, list):
            raise ValueError(f"Gemini returned invalid {field_name} data.")
    if not isinstance(setting, dict):
        setting = {}

    total_people = data.get("total_people", {})
    if not isinstance(total_people, dict):
        total_people = {}
    visible_count = total_people.get("visible_count")
    if not isinstance(visible_count, int) or isinstance(visible_count, bool) or visible_count < 0:
        visible_count = None
    try:
        confidence = max(0.0, min(1.0, float(total_people.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    setting["people_count"] = {
        "visible_count": visible_count,
        "confidence": confidence,
        "counting_notes": str(total_people.get("counting_notes", "")),
    }

    search_text = "\n".join([
        description,
        "People: " + ", ".join(map(str, people)),
        "Actions: " + ", ".join(map(str, actions)),
        "Emotions: " + ", ".join(map(str, emotions)),
        "Interactions: " + ", ".join(map(str, interactions)),
        "People count: " + json.dumps(setting["people_count"], ensure_ascii=False),
        "Setting: " + json.dumps(setting, ensure_ascii=False),
    ])

    PhotoSceneAnalysis.objects.update_or_create(
        photo=photo,
        defaults={
            "description": description,
            "people": people,
            "actions": actions,
            "emotions": emotions,
            "interactions": interactions,
            "setting": setting,
            "search_text": search_text,
            "model_name": GEMINI_MODEL_NAME,
        },
    )
    return True


def process_uploaded_photo(photo):
    """Process a saved photo and return per-model completion/errors."""
    try:
        image_bytes, image = _read_photo(photo)
    except Exception as error:
        logger.exception("Could not read uploaded photo %s", photo.pk)
        return {"clip": False, "gemini": False, "yolo": False, "errors": {"image": str(error)}}

    jobs = {
        "clip": lambda: _process_clip(photo, image),
        "gemini": lambda: _process_gemini(photo, image_bytes),
        "yolo": lambda: _process_yolo(photo, image),
    }
    outcomes = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {name: executor.submit(job) for name, job in jobs.items()}
        for name, future in futures.items():
            try:
                outcomes[name] = bool(future.result())
            except Exception as error:
                outcomes[name] = False
                errors[name] = f"{type(error).__name__}: {error}"
                logger.exception("%s processing failed for photo %s", name, photo.pk)

    return {**outcomes, "errors": errors}
