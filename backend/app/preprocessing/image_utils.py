"""
Image Preprocessing Service
Normalizes brightness, contrast, mild noise, and exposure
without permanently mutating the original uploaded image.
"""

import cv2
import numpy as np


def preprocess_image_for_analysis(image: np.ndarray) -> dict:
    """
    Produce a normalized copy of the input image for layout/OCR analysis.
    Keeps original and processed images strictly separate.
    """
    if image is None or image.size == 0:
        return {"original": None, "processed": None, "gray": None}

    # Maintain independent copy
    original_image = image.copy()
    processed = image.copy()

    # 1. Color space conversions
    if len(processed.shape) == 3:
        # Convert to LAB for luminance channel equalization (adaptive CLAHE)
        lab = cv2.cvtColor(processed, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L-channel to balance uneven lighting and shadows
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_equalized = clahe.apply(l)
        
        lab_equalized = cv2.merge((l_equalized, a, b))
        processed = cv2.cvtColor(lab_equalized, cv2.COLOR_LAB2BGR)
        gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
    else:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(processed)
        processed = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # 2. Mild denoising (Bilateral filter preserves text edges while smoothing sensor/JPEG noise)
    denoised_gray = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)

    return {
        "original": original_image,
        "processed": processed,
        "gray": gray,
        "denoised_gray": denoised_gray
    }
