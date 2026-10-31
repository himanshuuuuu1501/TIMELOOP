from functools import lru_cache

import numpy as np


MODEL_NAME = "openai/clip-vit-base-patch32"


@lru_cache(maxsize=1)
def load_clip_model():
    """
    Load CLIP only when a CLIP search or indexing operation is requested.
    The model is cached and reused for subsequent requests.
    """
    import torch
    from transformers import CLIPModel, CLIPProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    model = CLIPModel.from_pretrained(MODEL_NAME)
    model.to(device)
    model.eval()

    return processor, model, torch, device


def create_image_embedding(image):
    """
    Convert a PIL image into a normalized CLIP image embedding.
    """
    processor, model, torch, device = load_clip_model()
    inputs = processor(
        images=image.convert("RGB"),
        return_tensors="pt",
    )
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.no_grad():
        features = model.get_image_features(**inputs)
        if hasattr(features, "pooler_output"):
            features = features.pooler_output
        elif hasattr(features, "image_embeds"):
            features = features.image_embeds
        features = features / features.norm(dim=-1, keepdim=True)

    return features[0].cpu().numpy().astype(np.float32).tolist()


def create_text_embedding(text):
    """
    Convert a natural-language search query into a normalized CLIP embedding.
    """
    processor, model, torch, device = load_clip_model()
    inputs = processor(
        text=[text],
        return_tensors="pt",
        padding=True,
        truncation=True,
    )
    inputs = {key: value.to(device) for key, value in inputs.items()}

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
