import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from ultralytics import YOLO
from galleries.models import Photo

print("Loading YOLO model...")
model = YOLO("yolo26n.pt")

# Test one selfie and one car image
test_photo_ids = list(
    Photo.objects.values_list("id", flat=True).order_by("id")
)

for photo_id in test_photo_ids:
    try:
        photo = Photo.objects.get(id=photo_id)

        print("\n" + "=" * 50)
        print("Photo:", photo.original_filename)
        print("Photo ID:", photo.id)

        results = model.predict(
            source=photo.image.path,
            conf=0.25,
            verbose=False
        )

        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                print("No objects detected.")
                continue

            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                object_name = model.names[class_id]

                print(
                    f"{object_name}: {confidence:.3f}"
                )

    except Photo.DoesNotExist:
        print(f"Photo ID {photo_id} not found.")
    except Exception as error:
        print(f"Error testing photo {photo_id}: {error}")