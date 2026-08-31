"""
Perspective Correction and Normalization Service
Transforms distorted/skewed document captures into standardized rectangular coordinates.
"""

import cv2
import numpy as np
from app.models.legacy_document_detection import detect_document_corners


def correct_perspective_and_normalize(
    image: np.ndarray,
    target_width: int = 1000,
    target_height: int = 630,
    expected_ratio: float | None = None
) -> tuple[np.ndarray, dict]:
    """
    Performs perspective warping and normalization.
    Returns the rectified image (1000x630 standard) and transformation metadata.
    """
    if image is None or image.size == 0:
        return image, {"status": "failed", "applied": False, "error": "Empty image"}

    # Adjust dimensions if custom aspect ratio provided
    if expected_ratio and expected_ratio > 0:
        target_height = int(round(target_width / expected_ratio))

    corners, detection_meta = detect_document_corners(image)

    if corners is not None and detection_meta.get("status") == "detected":
        # Destination standard coordinates
        dst = np.array([
            [0, 0],
            [target_width - 1, 0],
            [target_width - 1, target_height - 1],
            [0, target_height - 1]
        ], dtype=np.float32)

        # Perspective transformation matrix
        M = cv2.getPerspectiveTransform(corners, dst)
        warped = cv2.warpPerspective(
            image,
            M,
            (target_width, target_height),
            flags=cv2.INTER_LANCZOS4
        )

        return warped, {
            "status": "success",
            "applied": True,
            "corners": corners.tolist(),
            "target_dimensions": {"width": target_width, "height": target_height},
            "detection": detection_meta
        }

    # Fallback: If document boundary not isolated (already tightly cropped), resize to target dimensions smoothly
    resized = cv2.resize(
        image,
        (target_width, target_height),
        interpolation=cv2.INTER_LANCZOS4
    )

    return resized, {
        "status": "fallback_resize",
        "applied": False,
        "reason": detection_meta.get("reason", "Standard direct normalization applied"),
        "target_dimensions": {"width": target_width, "height": target_height}
    }
