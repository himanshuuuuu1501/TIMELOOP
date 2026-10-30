
from django.core.management.base import BaseCommand
from django.db import transaction

from PIL import Image, ImageOps, UnidentifiedImageError

from galleries.models import Photo
from ml_engine.models import PhotoEmbedding
from ml_engine.clip_search import create_image_embedding


class Command(BaseCommand):
    help = "Generate and store CLIP embeddings for gallery photos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Rebuild embeddings for every photo.",
        )
        parser.add_argument(
            "--event",
            type=int,
            help="Index photos from a specific event ID only.",
        )

    def handle(self, *args, **options):
        photos = Photo.objects.all().order_by("id")

        if options["event"]:
            photos = photos.filter(event_id=options["event"])

        if not options["force"]:
            photos = photos.exclude(
                id__in=PhotoEmbedding.objects.values_list(
                    "photo_id", flat=True
                )
            )

        total = photos.count()

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS("No photos need indexing.")
            )
            return

        self.stdout.write(f"Photos to index: {total}")

        indexed = 0
        failed = 0

        for number, photo in enumerate(
            photos.iterator(chunk_size=100), 1
        ):
            try:
                with Image.open(photo.image.path) as source:
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    embedding = create_image_embedding(image)

                with transaction.atomic():
                    PhotoEmbedding.objects.update_or_create(
                        photo=photo,
                        defaults={
                            "embedding": embedding,
                            "model_name": "openai/clip-vit-base-patch32",
                        },
                    )

                indexed += 1
                self.stdout.write(
                    f"[{number}/{total}] Indexed photo {photo.id}: "
                    f"{photo.original_filename}"
                )

            except (
                OSError,
                ValueError,
                UnidentifiedImageError,
            ) as error:
                failed += 1
                self.stderr.write(
                    f"[{number}/{total}] Failed photo {photo.id}: {error}"
                )

            except Exception as error:
                failed += 1
                self.stderr.write(
                    f"[{number}/{total}] Unexpected error for photo "
                    f"{photo.id}: {type(error).__name__}: {error}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished. Indexed: {indexed}, failed: {failed}."
            )
        )
