"""
OCR Bounding Box & Text Analysis
Utilizes PaddleOCR with relative coordinate normalization.
"""

import os
from services.ocr_service import extract_ocr_data


def perform_ocr_analysis(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {
            "risk": 0,
            "status": "failed",
            "error": "File not found"
        }

    try:
        data = extract_ocr_data(image_path)
        if data.get("status") == "failed":
            return {
                "risk": 0,
                "status": "failed",
                "confidence": 0.0,
                "anomalies": [data.get("error", "OCR failure")],
                "boxes": [],
                "text": "",
                "detected_side": "unknown"
            }

        boxes = data.get("boxes", [])
        avg_conf = data.get("confidence", 0.0)
        full_text = data.get("text", "")
        detected_side = data.get("detected_side", "unknown")

        # Confidence-aware risk calculation
        # If OCR confidence is very low due to lighting/camera, do not aggressively penalize authenticity
        risk_score = 0
        if avg_conf < 0.30 and len(boxes) > 0:
            risk_score = 15  # Mild check
        elif len(boxes) == 0:
            risk_score = 25  # No readable text detected

        return {
            "status": "completed",
            "confidence": avg_conf,
            "risk": risk_score,
            "anomalies": [],
            "boxes": boxes,
            "text": full_text,
            "detected_side": detected_side,
            "engine": data.get("engine", "none")
        }

    except Exception as e:
        return {
            "status": "failed",
            "risk": 0,
            "error": str(e),
            "confidence": 0.0,
            "boxes": [],
            "text": "",
            "detected_side": "unknown"
        }