
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=api_key)

image_path = input("Enter the full path of a photo: ")

with open(image_path, "rb") as image_file:
    image_bytes = image_file.read()

response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=[
        """
        Analyse this photograph for a visual memory search application.

        Describe:
        1. People and their visible roles, without guessing identities.
        2. Actions and activities.
        3. Facial expressions and visible emotions.
        4. Interactions between people.
        5. Clothing and important visual attributes.
        6. Setting and event context.

        Pay special attention to subtle emotional moments.
        Do not invent details that cannot be confidently observed.

        Return a detailed, natural-language description.
        """,
        genai.types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        )
    ]
)

print("\nGEMINI ANALYSIS:\n")
print(response.text)
