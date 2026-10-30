
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from PIL import Image
from ml_engine.clip_search import (
    create_image_embedding,
    create_text_embedding,
    cosine_similarity,
)
from galleries.models import Photo

photo = Photo.objects.first()

if photo is None:
    print("No photos found. Upload a photo first.")
else:
    print("Testing photo:", photo.original_filename)

    with Image.open(photo.image.path) as image:
        image_embedding = create_image_embedding(image)

    print("Embedding dimensions:", len(image_embedding))

    descriptions = [
    "A selfie of a man wearing black glasses",
    "A person wearing a grey T-shirt",
    "A person wearing a T-shirt with a mountain graphic",
    "A person standing indoors in a bedroom",
    "A person wearing a blue shirt",
    "A bride and groom exchanging garlands",
    "People dancing at a wedding",
    "A person standing outdoors in a forest",
]

    print("\nText similarity results:")

    for description in descriptions:
        text_embedding = create_text_embedding(description)
        score = cosine_similarity(image_embedding, text_embedding)
        print(f"{description}: {score:.4f}")
