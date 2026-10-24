
import tkinter as tk
from tkinter import filedialog
import requests
from pathlib import Path

API_URL = "http://127.0.0.1:8000/api/search/person-search/"

root = tk.Tk()
root.withdraw()

photo_path = filedialog.askopenfilename(
    title="Choose your reference photo",
    filetypes=[
        ("Image files", "*.jpg *.jpeg *.png *.webp"),
        ("All files", "*.*"),
    ],
)

root.destroy()

if not photo_path:
    print("No photo selected.")
    raise SystemExit

with open(photo_path, "rb") as photo:
    response = requests.post(
        API_URL,
        files={
            "reference_image": (
                Path(photo_path).name,
                photo,
                "application/octet-stream",
            )
        },
        timeout=300,
    )

print("Status:", response.status_code)
print(response.text)
