"""
Reference-Based Layout Analysis

Compares the uploaded Aadhaar image against a genuine
reference image using alignment, aspect ratio and
structural similarity.
"""

import os
import cv2
import numpy as np

from reference.alignment import align_image


def perform_layout_analysis(image_path: str, reference_path: str) -> dict:

    if not os.path.exists(image_path):
        return {
            "status": "failed",
            "score": 0,
            "risk": 100,
            "error": "Uploaded image not found"
        }

    if not os.path.exists(reference_path):
        return {
            "status": "failed",
            "score": 0,
            "risk": 100,
            "error": "Reference image not found"
        }

    try:
        uploaded = cv2.imread(image_path)
        reference = cv2.imread(reference_path)

        if uploaded is None or reference is None:
            return {
                "status": "failed",
                "score": 0,
                "risk": 100,
                "error": "Could not read images"
            }

        # -------------------------------------------------
        # Aspect Ratio
        # -------------------------------------------------

        ref_height, ref_width = reference.shape[:2]
        img_height, img_width = uploaded.shape[:2]

        ref_ratio = ref_width / ref_height
        img_ratio = img_width / img_height

        ratio_difference = abs(
            ref_ratio - img_ratio
        ) / ref_ratio

        if ratio_difference <= 0.02:
            ratio_score = 100
        elif ratio_difference <= 0.05:
            ratio_score = 90
        elif ratio_difference <= 0.08:
            ratio_score = 75
        elif ratio_difference <= 0.12:
            ratio_score = 60
        else:
            ratio_score = 30

        # -------------------------------------------------
        # Align image with reference
        # -------------------------------------------------

        aligned, alignment_result = align_image(
            image_path,
            reference_path
        )

        if aligned is None:
            return {
                "status": "failed",
                "score": 0,
                "risk": 100,
                "error": alignment_result.get(
                    "error",
                    "Alignment failed"
                )
            }

        # -------------------------------------------------
        # Convert to grayscale
        # -------------------------------------------------

        aligned_gray = cv2.cvtColor(
            aligned,
            cv2.COLOR_BGR2GRAY
        )

        reference_gray = cv2.cvtColor(
            reference,
            cv2.COLOR_BGR2GRAY
        )

        # Ensure identical dimensions
        aligned_gray = cv2.resize(
            aligned_gray,
            (
                reference_gray.shape[1],
                reference_gray.shape[0]
            )
        )

        # -------------------------------------------------
        # Structural comparison
        # -------------------------------------------------

        # Blur slightly to reduce sensitivity to:
        # lighting, JPEG noise and tiny pixel differences.
        aligned_blur = cv2.GaussianBlur(
            aligned_gray,
            (5, 5),
            0
        )

        reference_blur = cv2.GaussianBlur(
            reference_gray,
            (5, 5),
            0
        )

        difference = cv2.absdiff(
            aligned_blur,
            reference_blur
        )

        mean_difference = float(
            difference.mean()
        )

        # Conservative structural score
        if mean_difference <= 10:
            structural_score = 100
        elif mean_difference <= 20:
            structural_score = 90
        elif mean_difference <= 30:
            structural_score = 80
        elif mean_difference <= 40:
            structural_score = 70
        elif mean_difference <= 55:
            structural_score = 55
        else:
            structural_score = 30

        # -------------------------------------------------
        # Alignment score
        # -------------------------------------------------

        if alignment_result.get("status") == "success":
            alignment_score = 100
        else:
            alignment_score = 60

        # -------------------------------------------------
        # Final Layout Score
        # -------------------------------------------------

        score = (
            structural_score * 0.45 +
            ratio_score * 0.25 +
            alignment_score * 0.30
        )

        score = int(
            round(
                max(
                    0,
                    min(100, score)
                )
            )
        )

        risk = 100 - score

        # -------------------------------------------------
        # Anomalies
        # -------------------------------------------------

        anomalies = []

        if ratio_difference > 0.05:
            anomalies.append(
                "Document aspect ratio differs from reference."
            )

        if mean_difference > 40:
            anomalies.append(
                "Significant structural difference from reference."
            )

        if alignment_result.get("status") != "success":
            anomalies.append(
                "Unable to confidently align document with reference."
            )

        return {
            "status": "completed",
            "score": score,
            "risk": risk,

            "alignment": alignment_result,

            "reference": {
                "width": ref_width,
                "height": ref_height,
                "aspect_ratio": round(ref_ratio, 4)
            },

            "uploaded": {
                "width": img_width,
                "height": img_height,
                "aspect_ratio": round(img_ratio, 4)
            },

            "measurements": {
                "ratio_difference": round(
                    ratio_difference,
                    4
                ),
                "mean_structural_difference": round(
                    mean_difference,
                    2
                )
            },

            "component_scores": {
                "structural": structural_score,
                "aspect_ratio": ratio_score,
                "alignment": alignment_score
            },

            "anomalies": anomalies
        }

    except Exception as e:
        return {
            "status": "failed",
            "score": 0,
            "risk": 100,
            "error": str(e)
        }