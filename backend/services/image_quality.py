"""
Image Quality Assessment Service
Evaluates sharpness, brightness, contrast, and resolution.
Explicitly separated from authenticity/tampering risk.
"""

import cv2
import numpy as np


def assess_image_quality(image: np.ndarray) -> dict:
    """
    Assess quality metrics of the uploaded image.
    Returns quality score (0-100), metrics, and descriptive flags.
    """
    if image is None or image.size == 0:
        return {
            "score": 0,
            "sharpness": 0,
            "brightness": 0,
            "contrast": 0,
            "resolution_adequate": False,
            "status": "poor",
            "warnings": ["Image could not be read or is empty"]
        }

    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

    # 1. Sharpness / Blur detection (Laplacian variance)
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if laplacian_var >= 300:
        sharpness_score = 100
    elif laplacian_var >= 100:
        sharpness_score = 70 + (laplacian_var - 100) / 200 * 30
    elif laplacian_var >= 30:
        sharpness_score = 40 + (laplacian_var - 30) / 70 * 30
    else:
        sharpness_score = max(10, laplacian_var / 30 * 40)

    # 2. Brightness evaluation (Ideal mean luminosity ~ 100-180)
    mean_brightness = float(np.mean(gray))
    if 100 <= mean_brightness <= 180:
        brightness_score = 100
    elif 60 <= mean_brightness < 100:
        brightness_score = 60 + (mean_brightness - 60) / 40 * 40
    elif 180 < mean_brightness <= 220:
        brightness_score = 100 - (mean_brightness - 180) / 40 * 35
    elif mean_brightness < 60:
        brightness_score = max(15, mean_brightness / 60 * 60)
    else:
        brightness_score = max(15, (255 - mean_brightness) / 35 * 65)

    # 3. Contrast evaluation (Standard deviation of pixel intensities)
    contrast_std = float(np.std(gray))
    if contrast_std >= 50:
        contrast_score = 100
    elif contrast_std >= 25:
        contrast_score = 50 + (contrast_std - 25) / 25 * 50
    else:
        contrast_score = max(10, contrast_std / 25 * 50)

    # 4. Resolution check
    resolution_adequate = (w >= 600 and h >= 380)
    if w >= 1000 and h >= 630:
        res_score = 100
    elif w >= 600 and h >= 380:
        res_score = 80
    elif w >= 400 and h >= 250:
        res_score = 55
    else:
        res_score = 30

    # Overall Image Quality Score
    quality_score = int(round(
        sharpness_score * 0.35 +
        brightness_score * 0.25 +
        contrast_score * 0.25 +
        res_score * 0.15
    ))
    quality_score = max(0, min(100, quality_score))

    warnings = []
    if sharpness_score < 45:
        warnings.append("Image is blurry; text legibility may be reduced.")
    if brightness_score < 45:
        if mean_brightness < 70:
            warnings.append("Image appears underexposed (too dark).")
        else:
            warnings.append("Image appears overexposed (harsh lighting / glare).")
    if contrast_score < 40:
        warnings.append("Low contrast between text and background.")
    if not resolution_adequate:
        warnings.append("Low image resolution. Higher resolution recommended.")

    return {
        "score": quality_score,
        "sharpness": round(sharpness_score, 1),
        "brightness": round(brightness_score, 1),
        "contrast": round(contrast_score, 1),
        "resolution": {
            "width": w,
            "height": h,
            "adequate": resolution_adequate
        },
        "metrics": {
            "laplacian_variance": round(laplacian_var, 2),
            "mean_brightness": round(mean_brightness, 2),
            "contrast_std": round(contrast_std, 2)
        },
        "warnings": warnings
    }
