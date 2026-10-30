
from functools import lru_cache

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


MODEL_NAME = "openai/clip-vit-base-patch32"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def load_clip_model():
    """
    Load CLIP once and reuse it for subsequent requests.
    The first run downloads the model if it is not cached.
    """
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    model = CLIPModel.from_pretrained(MODEL_NAME)
    model.to(DEVICE)
    model.eval()

    return processor, model


def create_image_embedding(image):
    """
    Convert a PIL image into a normalized CLIP image embedding.
    """
    processor, model = load_clip_model()

    inputs = processor(
        images=image.convert("RGB"),
        return_tensors="pt",
    )

    inputs = {key: value.to(DEVICE) for key, value in inputs.items()}

    with torch.no_grad():
        features = model.get_image_features(**inputs)

        # Support Transformers versions that return feature objects.
        if hasattr(features, "pooler_output"):
            features = features.pooler_output
        elif hasattr(features, "image_embeds"):
            features = features.image_embeds

        features = features / features.norm(dim=-1, keepdim=True)

    return features[0].cpu().numpy().astype(np.float32).tolist()


def create_text_embedding(text):
    """
    Convert a natural-language search query into a normalized embedding.
    """
    processor, model = load_clip_model()

    inputs = processor(
        text=[text],
        return_tensors="pt",
        padding=True,
        truncation=True,
    )

    inputs = {key: value.to(DEVICE) for key, value in inputs.items()}

    with torch.no_grad():
        features = model.get_text_features(**inputs)

        if hasattr(features, "pooler_output"):
            features = features.pooler_output
        elif hasattr(features, "text_embeds"):
            features = features.text_embeds

        features = features / features.norm(dim=-1, keepdim=True)

    return features[0].cpu().numpy().astype(np.float32)


def cosine_similarity(first, second):
    """
    Compare two normalized embeddings.
    Higher scores indicate greater similarity.
    """
    first = np.asarray(first, dtype=np.float32)
    second = np.asarray(second, dtype=np.float32)

    denominator = np.linalg.norm(first) * np.linalg.norm(second)

    if denominator == 0:
        return 0.0

    return float(np.dot(first, second) / denominator)
