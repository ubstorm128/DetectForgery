"""
OCR Bounding Box & Formatting Analysis
Extracts bounding boxes using Tesseract.

Typography comparison is handled separately using
the genuine Aadhaar reference template.
"""

import os

import pytesseract
from PIL import Image


def perform_ocr_analysis(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {
            "risk": 0,
            "status": "failed",
            "error": "File not found"
        }

    try:
        img = Image.open(image_path)

        # Extract OCR data with bounding boxes
        data = pytesseract.image_to_data(
            img,
            output_type=pytesseract.Output.DICT
        )

    except Exception as e:
        return {
            "risk": 0,
            "status": "failed",
            "error": str(e)
        }

    boxes = []
    n_boxes = len(data["text"])

    for i in range(n_boxes):
        if int(data["conf"][i]) > -1:
            text = data["text"][i].strip()

            if text:
                boxes.append({
                    "text": text,
                    "confidence": float(data["conf"][i]),
                    "x": int(data["left"][i]),
                    "y": int(data["top"][i]),
                    "width": int(data["width"][i]),
                    "height": int(data["height"][i])
                })

    if not boxes:
        return {
            "risk": 0,
            "status": "completed",
            "confidence": 0,
            "anomalies": []
        }

    # Average OCR confidence
    avg_conf = sum(
        b["confidence"] for b in boxes
    ) / len(boxes)

    # Typography comparison will be handled separately
    # using the genuine Aadhaar reference template.
    anomalies = []
    risk_score = 0

    # Cap risk score
    risk_score = min(risk_score, 100)

    # Concatenate OCR text for side detection
    full_text = " ".join(
        b["text"] for b in boxes
    ).lower()

    # Side Detection Heuristics
    detected_side = "unknown"

    front_keywords = [
        "dob",
        "year of birth",
        "male",
        "female",
        "name"
    ]

    back_keywords = [
        "address",
        "c/o",
        "s/o",
        "d/o",
        "w/o",
        "pincode",
        "uidai.gov.in",
        "1947"
    ]

    front_score = sum(
        1 for kw in front_keywords
        if kw in full_text
    )

    back_score = sum(
        1 for kw in back_keywords
        if kw in full_text
    )

    if front_score > back_score:
        detected_side = "front"
    elif back_score > front_score:
        detected_side = "back"

    return {
        "status": "completed",
        "confidence": avg_conf,
        "risk": risk_score,
        "anomalies": anomalies[:5],
        "boxes": boxes,
        "text": full_text,
        "detected_side": detected_side
    }