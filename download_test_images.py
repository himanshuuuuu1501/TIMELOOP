
import csv
import html
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError

OUTPUT_DIR = Path("test_images")
MAX_PER_CATEGORY = 12
THUMBNAIL_WIDTH = 640

CATEGORIES = {
    "dogs": "dogs",
    "cats": "cats",
    "cars": "cars",
    "food": "food photography",
    "flowers": "flowers",
    "landscapes": "landscape photography",
    "beaches": "beaches",
    "people": "people in everyday life",
}

API_URL = "https://commons.wikimedia.org/w/api.php"

session = requests.Session()
session.headers.update({
    "User-Agent": "TIMELOOPResearchPrototype/1.0 "
                  "(educational image retrieval experiment)"
})

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
metadata_path = OUTPUT_DIR / "metadata.csv"

downloaded = 0
seen_urls = set()

with metadata_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
    writer = csv.DictWriter(
        csvfile,
        fieldnames=[
            "filename",
            "category",
            "title",
            "source_page",
            "license",
            "license_url",
            "artist",
        ],
    )
    writer.writeheader()

    for category, search_term in CATEGORIES.items():
        category_dir = OUTPUT_DIR / category
        category_dir.mkdir(exist_ok=True)

        print(f"\nSearching for: {category}")
        saved_in_category = 0

        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": search_term,
            "gsrnamespace": 6,
            "gsrlimit": 30,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|mime",
            "iiurlwidth": THUMBNAIL_WIDTH,
        }

        try:
            response = session.get(
                API_URL, params=params, timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as error:
            print(f"Search failed for {category}: {error}")
            continue

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            if saved_in_category >= MAX_PER_CATEGORY:
                break

            info_list = page.get("imageinfo", [])
            if not info_list:
                continue

            info = info_list[0]
            mime = info.get("mime", "")
            if not mime.startswith("image/"):
                continue

            image_url = info.get("thumburl") or info.get("url")
            if not image_url or image_url in seen_urls:
                continue

            seen_urls.add(image_url)

            # Keep the filename safe for Windows.
            title = page.get("title", "image")
            safe_title = re.sub(
                r'[<>:"/\\|?*\x00-\x1f]', "_", title
            )[:90].strip(" ._")

            extension = Path(urlparse(image_url).path).suffix.lower()
            if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
                extension = ".jpg"

            filename = f"{category}_{saved_in_category + 1:03d}{extension}"
            destination = category_dir / filename

            try:
                image_response = session.get(
                    image_url, timeout=30
                )
                image_response.raise_for_status()

                # Avoid unexpectedly large downloads.
                if len(image_response.content) > 8 * 1024 * 1024:
                    print(f"Skipped oversized image: {title}")
                    continue

                destination.write_bytes(image_response.content)

                # Verify that the downloaded file is a readable image.
                with Image.open(destination) as image:
                    image.verify()

            except (
                requests.RequestException,
                UnidentifiedImageError,
                OSError,
            ) as error:
                destination.unlink(missing_ok=True)
                print(f"Skipped {title}: {error}")
                continue

            metadata = info.get("extmetadata", {})

            def metadata_value(key):
                value = metadata.get(key, {})
                return html.unescape(value.get("value", ""))

            writer.writerow({
                "filename": str(destination),
                "category": category,
                "title": title,
                "source_page": info.get("descriptionurl", ""),
                "license": metadata_value("LicenseShortName"),
                "license_url": metadata_value("LicenseUrl"),
                "artist": metadata_value("Artist"),
            })
            csvfile.flush()

            saved_in_category += 1
            downloaded += 1
            print(
                f"[{downloaded}] Saved {category}: "
                f"{filename}"
            )

            # Be polite to the public API.
            time.sleep(0.5)

        print(
            f"{category}: saved {saved_in_category} images"
        )

print("\nDownload finished.")
print(f"Total images saved: {downloaded}")
print(f"Image folder: {OUTPUT_DIR.resolve()}")
print(f"Metadata CSV: {metadata_path.resolve()}")
print("Review individual image licenses before reuse.")
