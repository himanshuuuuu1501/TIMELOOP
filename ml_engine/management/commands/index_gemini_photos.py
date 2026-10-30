
import json
import mimetypes
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from dotenv import load_dotenv
from google import genai
from google.genai import types

from galleries.models import Photo
from ml_engine.models import PhotoSceneAnalysis


MODEL_NAME = "gemini-3.8-flash"
MAX_RETRIES = 4


PROMPT = """
You are an expert visual scene analyst for TIMELOOP,
a natural-language photo memory search system.

Analyse the entire photograph carefully.

Return ONLY valid JSON in this exact structure:

{
  "description": "Detailed description of the photograph.",
  "people": [],
  "total_people": {
    "visible_count": 0,
    "confidence": 0.0,
    "counting_notes": ""
  },
  "actions": [],
  "emotions": [],
  "interactions": [],
  "setting": {
    "location": "",
    "event": "",
    "time": "",
    "details": []
  }
}

PEOPLE COUNTING RULES:

1. Count distinct visible human beings in the entire image.
2. Count each person only once.
3. Do not count reflections, photographs, posters or statues as people.
4. Include partially visible people only when they can
   reasonably be identified as distinct individuals.
5. Do not guess the number of people hidden behind others.
6. If an exact count is impossible, use null for visible_count.
7. Confidence must be between 0.0 and 1.0.
8. Explain uncertainty in counting_notes.
9. Never confuse the number of people performing an action
   with the total number of people in the photograph.

ACTION RULES:

1. Identify specific actions such as hugging, kissing,
   standing, sitting, dancing, crying and laughing.
2. Identify how many people are visibly involved in each
   action whenever possible.
3. Distinguish between people standing together and people
   actively interacting.
4. Do not claim that people are hugging merely because
   they are standing close together.
5. Do not claim someone is laughing unless there is
   visible evidence.
6. Describe interactions between people.

GENERAL RULES:

1. Describe only observable visual evidence.
2. Never invent relationships, identities or emotions.
3. Do not assume an event is a wedding without evidence.
4. Do not identify real people's names.
5. Use empty arrays or strings when information is unavailable.
6. Be detailed enough to support natural-language searches.
7. Return valid JSON only.
"""



def analyse_with_retry(client, image_bytes, mime_type):
    """Send an image to Gemini with automatic retries."""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    PROMPT,
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )

            if not response.text:
                raise ValueError("Gemini returned an empty response.")

            return json.loads(response.text)

        except Exception as error:
            if attempt == MAX_RETRIES - 1:
                raise

            wait_time = 2 ** (attempt + 1)

            print(
                f"  Attempt {attempt + 1} failed: {error}",
                flush=True
            )
            print(
                f"  Retrying in {wait_time} seconds...",
                flush=True
            )

            time.sleep(wait_time)

    raise RuntimeError("Gemini analysis failed after all retries.")


class Command(BaseCommand):
    help = "Generate Gemini visual scene analyses for TIMELOOP photos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--event",
            type=int,
            help="Only analyse photos belonging to this event ID."
        )

        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of photos to process."
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Reanalyse photos that already have scene analyses."
        )

    def handle(self, *args, **options):

        load_dotenv(os.path.join(settings.BASE_DIR, ".env"))

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            self.stderr.write(
                self.style.ERROR("GEMINI_API_KEY not found in .env")
            )
            return

        client = genai.Client(api_key=api_key)

        photos = Photo.objects.all().order_by("id")

        if options["event"] is not None:
            photos = photos.filter(event_id=options["event"])

        if not options["force"]:
            photos = photos.exclude(scene_analysis__isnull=False)

        if options["limit"] is not None:
            photos = photos[:options["limit"]]

        total = photos.count()

        if total == 0:
            self.stdout.write(
                self.style.WARNING("No new photos to analyse.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Gemini analysis for {total} photos..."
            )
        )

        successful = 0
        failed = 0

        for index, photo in enumerate(photos, start=1):

            self.stdout.write(
                f"\n[{index}/{total}] Analysing photo ID {photo.id}..."
            )

            try:
                if not photo.image:
                    raise FileNotFoundError("Photo has no image.")

                image_path = photo.image.path

                if not os.path.exists(image_path):
                    raise FileNotFoundError(
                        f"Image file not found: {image_path}"
                    )

                mime_type, _ = mimetypes.guess_type(image_path)

                if not mime_type or not mime_type.startswith("image/"):
                    mime_type = "image/jpeg"

                with open(image_path, "rb") as image_file:
                    image_bytes = image_file.read()

                self.stdout.write(
                    f"  Image size: {len(image_bytes) / 1024:.1f} KB"
                )

                data = analyse_with_retry(
                    client,
                    image_bytes,
                    mime_type
                )

                description = data.get("description", "")
                people = data.get("people", [])
                actions = data.get("actions", [])
                emotions = data.get("emotions", [])
                interactions = data.get("interactions", [])
                setting = data.get("setting", {})

                if not isinstance(setting, dict):
                    raise ValueError("Invalid setting format.")

                people_count = data.get("total_people", {})

                if not isinstance(people_count, dict):
                    people_count = {}

                visible_count = people_count.get("visible_count")

                if visible_count is not None:
                    if (
                        not isinstance(visible_count, int)
                        or isinstance(visible_count, bool)
                        or visible_count < 0
                    ):
                        raise ValueError("Invalid people count.")

                confidence = people_count.get("confidence", 0.0)

                if not isinstance(confidence, (int, float)):
                    confidence = 0.0

                confidence = max(0.0, min(1.0, float(confidence)))

                setting["people_count"] = {
                    "visible_count": visible_count,
                    "confidence": confidence,
                    "counting_notes": str(
                        people_count.get("counting_notes", "")
                    )
                }

                # Validate the returned structure.
                if not isinstance(description, str):
                    raise ValueError("Invalid description format.")

                for field_name, field_value in [
                    ("people", people),
                    ("actions", actions),
                    ("emotions", emotions),
                    ("interactions", interactions),
                ]:
                    if not isinstance(field_value, list):
                        raise ValueError(
                            f"Invalid {field_name} format."
                        )

                

                search_parts = [
                    description,
                    "People: " + ", ".join(map(str, people)),
                    "Actions: " + ", ".join(map(str, actions)),
                    "Emotions: " + ", ".join(map(str, emotions)),
                    "Interactions: " + ", ".join(map(str, interactions)),
                    "People count: " + json.dumps(
                        setting["people_count"],
                        ensure_ascii=False
                    ),
                    "Setting: " + json.dumps(
                        setting,
                        ensure_ascii=False
                    )
                ]

                search_text = "\n".join(search_parts)

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
                        "model_name": MODEL_NAME
                    }
                )

                successful += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"SUCCESS: Photo {photo.id} indexed."
                    )
                )

                self.stdout.write(
                    f"  Actions: {', '.join(map(str, actions[:5]))}"
                )

                self.stdout.write(
                    f"  Emotions: {', '.join(map(str, emotions[:5]))}"
                )

                # Small delay between successful requests.
                time.sleep(1)

            except Exception as error:
                failed += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"FAILED: Photo {photo.id}: {error}"
                    )
                )

        self.stdout.write("\n" + "=" * 45)
        self.stdout.write("GEMINI INDEXING COMPLETE")
        self.stdout.write(f"Total selected: {total}")
        self.stdout.write(
            self.style.SUCCESS(f"Successful: {successful}")
        )
        self.stdout.write(
            self.style.ERROR(f"Failed: {failed}")
        )
        self.stdout.write(
            f"Total scene analyses in database: "
            f"{PhotoSceneAnalysis.objects.count()}"
        )
        self.stdout.write("=" * 45)
