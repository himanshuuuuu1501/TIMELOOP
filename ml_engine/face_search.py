
import cv2
import numpy as np
from insightface.app import FaceAnalysis

_face_app = None


def get_face_app():
    global _face_app

    if _face_app is None:
        _face_app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        _face_app.prepare(ctx_id=-1, det_size=(640, 640))

    return _face_app


def extract_face_embeddings(image):
    image_array = np.asarray(image.convert("RGB"))
    success, encoded_image = cv2.imencode(
        ".jpg",
        cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR),
    )

    if not success:
        return []

    image_array = cv2.imdecode(encoded_image, cv2.IMREAD_COLOR)

    if image_array is None:
        return []

    faces = get_face_app().get(image_array)
    print("DEBUG input:", image_array.shape, image_array.dtype, image_array.min(), image_array.max())
    print("DEBUG detected faces:", len(faces))

    embeddings = []

    for face in faces:
        embedding = face.normed_embedding

        if embedding is not None:
            embeddings.append(
                np.asarray(embedding, dtype=np.float32)
            )

    return embeddings


def compare_embeddings(reference_embedding, candidate_embedding):
    reference_embedding = np.asarray(reference_embedding, dtype=np.float32)
    candidate_embedding = np.asarray(candidate_embedding, dtype=np.float32)

    reference_norm = np.linalg.norm(reference_embedding)
    candidate_norm = np.linalg.norm(candidate_embedding)

    if reference_norm == 0 or candidate_norm == 0:
        return 0.0

    return float(
        np.dot(
            reference_embedding / reference_norm,
            candidate_embedding / candidate_norm,
        )
    )
