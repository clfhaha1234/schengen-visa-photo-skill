from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image


DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"


@dataclass(frozen=True)
class FaceGeometry:
    chin_y: float
    crown_y: float
    head_height: float
    head_width: float
    center_x: float
    source: str = "face_landmarks"


def ensure_model(model_path: Path, model_url: str = DEFAULT_MODEL_URL) -> Path:
    if model_path.exists():
        return model_path
    model_path.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(model_url, model_path)
    return model_path


def detect_face_landmarks(image: Image.Image, model_path: Path, model_url: str = DEFAULT_MODEL_URL) -> np.ndarray:
    model_path = ensure_model(model_path, model_url)
    arr = np.asarray(image.convert("RGB"))
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
    )
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp_image)
    if not result.face_landmarks:
        raise RuntimeError("No face detected")

    height, width = arr.shape[:2]
    return np.array([(lm.x * width, lm.y * height) for lm in result.face_landmarks[0]], dtype=np.float32)


CHIN = 152
FOREHEAD = 10
LEFT_CHEEK = 234
RIGHT_CHEEK = 454
FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]


def estimate_face_geometry(points: np.ndarray, crown_extension_ratio: float = 0.12) -> FaceGeometry:
    chin_y = float(points[CHIN, 1])
    forehead_y = float(points[FOREHEAD, 1])
    face_height = chin_y - forehead_y
    if face_height <= 0:
        raise RuntimeError("Invalid face geometry: chin must be below forehead")

    crown_y = forehead_y - crown_extension_ratio * face_height
    oval = points[FACE_OVAL]
    head_width = float(np.max(oval[:, 0]) - np.min(oval[:, 0]))
    center_x = float((points[LEFT_CHEEK, 0] + points[RIGHT_CHEEK, 0]) / 2)
    return FaceGeometry(
        chin_y=chin_y,
        crown_y=crown_y,
        head_height=chin_y - crown_y,
        head_width=head_width,
        center_x=center_x,
    )


def estimate_background_color(arr: np.ndarray, border_px: int = 12) -> np.ndarray:
    """Estimate the plain-background color from regions that are reliably
    background in a head-and-shoulders portrait.

    The subject is centered with the head near the top and the shoulders
    widening toward the bottom, so the bottom corners frequently contain skin
    or clothing rather than background; sampling them biases the estimate (and
    the resulting pad fill) toward a skin tone. Instead, sample the top edge and
    the upper halves of the left and right edges, which are background in a
    standard portrait. The median is robust to the minority of hair pixels that
    may intrude at the top center, and adapts to white or light-grey alike.
    """
    h, w = arr.shape[:2]
    bw = max(4, min(border_px, h // 4, w // 4))
    samples = np.concatenate(
        [
            arr[:bw, :].reshape(-1, 3),          # top edge (full width)
            arr[: h // 2, :bw].reshape(-1, 3),   # upper-left edge
            arr[: h // 2, -bw:].reshape(-1, 3),  # upper-right edge
        ],
        axis=0,
    )
    return np.median(samples, axis=0)


def estimate_head_geometry_from_plain_background(
    image: Image.Image,
    points: np.ndarray,
    bg_tolerance: float = 32.0,
) -> FaceGeometry:
    """Estimate head geometry from the foreground silhouette on a plain background.

    Face landmarks reliably locate the face center and chin, but they do not
    know hair/crown boundaries. For plain-background ID photos the head
    silhouette is more direct evidence for top-of-head than landmarks. The
    background color is estimated from the corners so this works for white and
    light-grey Schengen backgrounds alike.
    """
    arr = np.asarray(image.convert("RGB")).astype(np.int16)
    bg = estimate_background_color(arr)
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))

    # Pixels far from the background color are foreground (hair/skin/clothing).
    mask = (dist > bg_tolerance).astype(np.uint8) * 255
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    chin_y = float(points[CHIN, 1])
    center_x = float((points[LEFT_CHEEK, 0] + points[RIGHT_CHEEK, 0]) / 2)
    landmark_width = float(np.max(points[FACE_OVAL, 0]) - np.min(points[FACE_OVAL, 0]))

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        raise RuntimeError("No foreground silhouette found on plain background")

    x = int(round(center_x))
    y = int(round(chin_y))
    label = labels[min(max(y, 0), labels.shape[0] - 1), min(max(x, 0), labels.shape[1] - 1)]
    if label == 0:
        # If the exact chin pixel is not inside the foreground, use the largest
        # non-background component. This is usually the head+body component.
        label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))

    comp = labels == label
    h, w = comp.shape
    band_half_width = max(int(landmark_width * 1.15), 80)
    x0 = max(0, int(center_x - band_half_width))
    x1 = min(w, int(center_x + band_half_width))
    y1 = min(h, int(chin_y + landmark_width * 0.20))
    upper_band = comp[:y1, x0:x1]
    ys, xs = np.where(upper_band)
    if len(ys) == 0:
        raise RuntimeError("Foreground silhouette does not overlap face band")

    crown_y = float(np.min(ys))
    head_height = chin_y - crown_y
    if head_height <= 0:
        raise RuntimeError("Invalid silhouette geometry: chin must be below crown")

    # Use the silhouette for top-of-head, but keep the Face Mesh oval for width.
    # The full silhouette often over-counts hair, neck, or jaw shadows, while the
    # oval tracks the stable facial outline used by the width band.
    head_width = landmark_width

    return FaceGeometry(
        chin_y=chin_y,
        crown_y=crown_y,
        head_height=head_height,
        head_width=head_width,
        center_x=center_x,
        source="plain_background_silhouette",
    )
