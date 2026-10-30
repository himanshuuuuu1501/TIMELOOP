
import os
import csv
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from ultralytics import YOLO
from galleries.models import Photo

model = YOLO("yolo26n.pt")

output_file = "ml_engine/yolo_evaluation.csv"

photos = Photo.objects.all().order_by("id")

rows = []

for photo in photos:
    print(f"Evaluating photo {photo.id}...")

    result_025 = model.predict(
        source=photo.image.path,
        conf=0.25,
        verbose=False
    )[0]

    result_010 = model.predict(
        source=photo.image.path,
        conf=0.10,
        verbose=False
    )[0]

    def extract_detections(result):
        detections = []

        if result.boxes is not None:
            for box in result.boxes:
                name = model.names[int(box.cls[0])]
                confidence = float(box.conf[0])

                detections.append(
                    f"{name} ({confidence:.3f})"
                )

        return "; ".join(detections)

    rows.append({
        "photo_id": photo.id,
        "filename": photo.original_filename,
        "detections_025": extract_detections(result_025),
        "detections_010": extract_detections(result_010),
        "actual_objects": "",
        "correct_detections": "",
        "missed_objects": "",
        "notes": ""
    })

fieldnames = [
    "photo_id",
    "filename",
    "detections_025",
    "detections_010",
    "actual_objects",
    "correct_detections",
    "missed_objects",
    "notes"
]

with open(output_file, "w", newline="", encoding="utf-8-sig") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("\nEvaluation completed!")
print(f"Total photos: {len(rows)}")
print(f"CSV saved at: {output_file}")
