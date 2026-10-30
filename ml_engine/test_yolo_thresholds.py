import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from ultralytics import YOLO
from galleries.models import Photo

model = YOLO("yolo26n.pt")

photos = Photo.objects.all().order_by("id")

for photo in photos:
    print("\n" + "=" * 55)
    print(f"Photo ID: {photo.id} | {photo.original_filename}")

    results = model.predict(
        source=photo.image.path,
        conf=0.10,
        verbose=False
    )

    for result in results:
        if result.boxes is None or len(result.boxes) == 0:
            print("No objects detected.")
            continue

        for box in result.boxes:
            name = model.names[int(box.cls[0])]
            confidence = float(box.conf[0])

            print(f"{name}: {confidence:.3f}")