"""
Document Detection Service
Finds document boundaries and 4-point polygon contours.
"""

import cv2
import numpy as np


def order_points(pts: np.ndarray) -> np.ndarray:
    """
    Order coordinates consistently:
    [top-left, top-right, bottom-right, bottom-left]
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left has smallest sum (x+y)
    rect[2] = pts[np.argmax(s)]  # bottom-right has largest sum (x+y)

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right has smallest difference (y-x)
    rect[3] = pts[np.argmax(diff)]  # bottom-left has largest difference (y-x)

    return rect


def detect_document_corners(image: np.ndarray) -> tuple[np.ndarray | None, dict]:
    """
    Detects document boundary corners in the image.
    Returns ordered 4-point polygon coordinates if found, along with confidence metadata.
    """
    if image is None or image.size == 0:
        return None, {"status": "failed", "confidence": 0.0, "reason": "Empty image"}

    h, w = image.shape[:2]
    total_area = h * w

    # Convert to grayscale & blur
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Edge detection & morphological closing to connect card borders
    edged = cv2.Canny(blurred, 50, 200)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    closed = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    best_corners = None
    best_area = 0
    confidence = 0.0

    for c in contours:
        area = cv2.contourArea(c)
        # ID card must occupy a reasonable portion of the frame (e.g. > 15% of frame)
        if area < total_area * 0.15:
            continue

        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)

        if len(approx) == 4:
            # Check convex
            if cv2.isContourConvex(approx):
                best_corners = approx.reshape(4, 2)
                best_area = area
                confidence = min(1.0, area / (total_area * 0.7))
                break

    # If 4-point polygon not strictly found, try finding the bounding rectangle of the largest card-like contour
    if best_corners is None and len(contours) > 0:
        c = contours[0]
        area = cv2.contourArea(c)
        if area > total_area * 0.25:
            rect = cv2.minAreaRect(c)
            box = cv2.boxPoints(rect)
            best_corners = np.intp(box)
            confidence = 0.65

    if best_corners is not None:
        ordered = order_points(best_corners.astype(np.float32))
        return ordered, {
            "status": "detected",
            "confidence": round(float(confidence), 2),
            "area_ratio": round(float(best_area / total_area if total_area > 0 else 0), 2)
        }

    return None, {
        "status": "not_detected",
        "confidence": 0.0,
        "reason": "Could not identify distinct 4-corner document boundaries"
    }
