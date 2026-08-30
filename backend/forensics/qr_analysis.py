"""
QR Code Analysis
Detects and decodes QR codes using OpenCV.
"""

import os
import cv2


def perform_qr_analysis(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {
            "status": "failed",
            "risk": 100,
            "error": "File not found"
        }

    try:
        image = cv2.imread(image_path)

        if image is None:
            return {
                "status": "failed",
                "risk": 100,
                "error": "Could not read image"
            }

        detector = cv2.QRCodeDetector()

        # Detect and decode QR
        data, points, _ = detector.detectAndDecode(image)

        # QR not detected
        if points is None:
            return {
                "status": "completed",
                "detected": False,
                "decoded": False,
                "data": None,
                "risk": 30,
                "bbox": None,
                "message": "No QR code detected"
            }

        # Convert points to integer coordinates
        points = points[0].astype(int)

        x_values = points[:, 0]
        y_values = points[:, 1]

        bbox = {
            "x": int(x_values.min()),
            "y": int(y_values.min()),
            "width": int(x_values.max() - x_values.min()),
            "height": int(y_values.max() - y_values.min())
        }

        # QR detected but could not be decoded
        if not data:
            return {
                "status": "completed",
                "detected": True,
                "decoded": False,
                "data": None,
                "risk": 50,
                "bbox": bbox,
                "message": "QR detected but could not be decoded"
            }

        # QR successfully decoded
        return {
            "status": "completed",
            "detected": True,
            "decoded": True,
            "data": data,
            "risk": 0,
            "bbox": bbox,
            "message": "QR code detected and decoded successfully"
        }

    except Exception as e:
        return {
            "status": "failed",
            "risk": 100,
            "error": str(e)
        }