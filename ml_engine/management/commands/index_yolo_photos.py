from django.core.management.base import BaseCommand
from django.db import transaction

from PIL import Image, ImageOps, UnidentifiedImageError
from ultralytics import YOLO

from galleries.models import Photo
from ml_engine.models import PhotoYOLOIndex


class Command(BaseCommand):
    help = "Detect and store objects in gallery photos using YOLO."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rebuild YOLO detections for every photo.",
        )
        parser.add_argument(
            "--event",
            type=int,
            help="Index photos from a specific event ID only.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of photos to process.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Loading YOLO model...")
        model = YOLO("yolo26n.pt")

        photos = Photo.objects.all().order_by("id")

        if options["event"] is not None:
            photos = photos.filter(event_id=options["event"])

        if not options["force"]:
            photos = photos.exclude(
                id__in=PhotoYOLOIndex.objects.values_list(
                    "photo_id", flat=True
                )
            )

        if options["limit"] is not None:
            photos = photos[:options["limit"]]

        total = photos.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No photos need indexing."))
            return

        self.stdout.write(f"Photos to process: {total}")
        indexed = 0
        failed = 0

        for number, photo in enumerate(photos.iterator(chunk_size=100), 1):
            try:
                if not photo.image:
                    raise FileNotFoundError("Photo has no image.")

                # YOLO accepts a PIL image. Open through storage so Cloudinary
                # and other non-local storage backends are supported.
                with photo.image.open("rb") as image_file:
                    with Image.open(image_file) as source:
                        image = ImageOps.exif_transpose(source).convert("RGB")
                        results = model.predict(
                            source=image,
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
                            "bbox": [
                                round(value, 2) for value in coordinates
                            ],
                        })

                with transaction.atomic():
                    PhotoYOLOIndex.objects.update_or_create(
                        photo=photo,
                        defaults={
                            "detections": detections,
                            "model_name": "yolo26n",
                        },
                    )

                indexed += 1
                self.stdout.write(
                    f"[{number}/{total}] Photo {photo.id}: "
                    f"{len(detections)} detections"
                )

            except (OSError, ValueError, UnidentifiedImageError) as error:
                failed += 1
                self.stderr.write(
                    f"Photo {photo.id} failed: {type(error).__name__}: {error}"
                )
            except Exception as error:
                failed += 1
                self.stderr.write(
                    f"Photo {photo.id} failed: "
                    f"{type(error).__name__}: {error}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\\nFinished! Indexed: {indexed}, Failed: {failed}"
            )
        )
