"""
OCR Service with PaddleOCR.
Extracts text, bounding boxes, confidence, and normalized relative coordinates.
Includes image preprocessing for mobile photos and Aadhaar number extraction/masking.
"""

import os
import re
import cv2
import numpy as np
import traceback

# Global OCR engine singleton
_paddle_ocr_engine = None
_paddle_available = None


def get_paddle_ocr():
    global _paddle_ocr_engine, _paddle_available
    if _paddle_available is False:
        return None
    if _paddle_ocr_engine is not None:
        return _paddle_ocr_engine

    try:
        from paddleocr import PaddleOCR
        # Initialize PaddleOCR with Hindi (which includes English and Devanagari)
        try:
            # Handle PaddleOCR 3.x (paddlex) PIR bugs by disabling mkldnn
            _paddle_ocr_engine = PaddleOCR(use_angle_cls=False, lang="hi", enable_mkldnn=False)
        except Exception:
            _paddle_ocr_engine = PaddleOCR(use_angle_cls=False, lang="hi")
        _paddle_available = True
        return _paddle_ocr_engine
    except Exception as e:
        print("\n" + "!"*40)
        print("PADDLEOCR INITIALIZATION FAILED:")
        traceback.print_exc()
        print("!"*40 + "\n")
        _paddle_available = False
        return None


def preprocess_for_ocr(img_bgr: np.ndarray) -> np.ndarray:
    """
    Apply image preprocessing (contrast, brightness, unsharp mask)
    to improve OCR accuracy on mobile photographs.
    """
    # 1. Convert to LAB color space to work on lightness
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    # 2. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l_channel)
    
    # 3. Merge back and convert to BGR
    limg = cv2.merge((cl, a_channel, b_channel))
    enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    # 4. Unsharp masking to sharpen text
    gaussian = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
    sharpened = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
    
    return sharpened


def _detect_document_side_heuristic(img_bgr: np.ndarray, full_text: str) -> str:
    """
    Combines text keywords and visual structural cues (Photo vs QR location)
    to accurately distinguish Front vs Back of Aadhaar card.
    """
    # 1. Check text keywords
    front_keywords = ["dob", "birth", "male", "female", "year of birth", "enrolment", "identity", "government of india", "mera aadhaar", "father"]
    back_keywords = ["address", "c/o", "s/o", "d/o", "w/o", "pincode", "pin code", "uidai.gov.in", "1947", "help@uidai", "unique identification", "helpdesk"]

    front_matches = sum(1 for kw in front_keywords if kw in full_text)
    back_matches = sum(1 for kw in back_keywords if kw in full_text)

    if front_matches > back_matches and front_matches > 0:
        return "front"
    if back_matches > front_matches and back_matches > 0:
        return "back"

    # 2. Visual layout heuristic if text is minimal or obscured
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if len(img_bgr.shape) == 3 else img_bgr

    # Check for QR code in image
    qr_detector = cv2.QRCodeDetector()
    _, points, _ = qr_detector.detectAndDecode(img_bgr)
    if points is not None and len(points) > 0:
        pts = points[0]
        qr_cx = np.mean(pts[:, 0]) / w
        if qr_cx > 0.50:
            return "back"

    # Check photo region variance
    left_roi = gray[int(h * 0.25):int(h * 0.75), int(w * 0.05):int(w * 0.35)]
    right_roi = gray[int(h * 0.25):int(h * 0.75), int(w * 0.65):int(w * 0.95)]

    left_var = float(np.var(left_roi)) if left_roi.size > 0 else 0
    right_var = float(np.var(right_roi)) if right_roi.size > 0 else 0

    if left_var > 400 and left_var > right_var * 1.1:
        return "front"
    elif right_var > 600 and right_var > left_var:
        return "back"

    return "front"


def extract_ocr_data(image: np.ndarray | str) -> dict:
    """
    Extract OCR items with bounding boxes, confidence, and normalized relative coordinates.
    """
    if isinstance(image, str):
        if not os.path.exists(image):
            return {
                "status": "failed",
                "boxes": [],
                "text": "",
                "confidence": 0.0,
                "detected_side": "front",
                "error": "File not found",
                "engine": "none"
            }
        img_bgr = cv2.imread(image)
        if img_bgr is None:
            return {
                "status": "failed",
                "boxes": [],
                "text": "",
                "confidence": 0.0,
                "detected_side": "front",
                "error": "Could not read image file",
                "engine": "none"
            }
    else:
        img_bgr = image.copy()

    h, w = img_bgr.shape[:2]
    if h == 0 or w == 0:
        return {
            "status": "failed",
            "boxes": [],
            "text": "",
            "confidence": 0.0,
            "detected_side": "front",
            "error": "Zero dimension image",
            "engine": "none"
        }

    paddle_engine = get_paddle_ocr()
    if paddle_engine is None:
        return {
            "status": "failed",
            "boxes": [],
            "text": "",
            "confidence": 0.0,
            "detected_side": "unknown",
            "error": "PaddleOCR engine is unavailable or failed to initialize",
            "engine": "none"
        }

    # Preprocess image and upscale by 2x only if small, to avoid OOM crashes
    try:
        processed_img = preprocess_for_ocr(img_bgr)
        if max(h, w) < 1200:
            processed_img = cv2.resize(processed_img, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    except Exception as e:
        if max(h, w) < 1200:
            processed_img = cv2.resize(img_bgr, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        else:
            processed_img = img_bgr
        print(f"Warning: preprocessing failed: {e}")

    boxes = []
    try:
        results = paddle_engine.ocr(processed_img)
        
        if results and len(results) > 0 and results[0] is not None:
            res_item = results[0]
            parsed_lines = []
            
            # Handle PaddleOCR 3.x dict format vs 2.x list format
            if isinstance(res_item, dict):
                texts = res_item.get('rec_texts', [])
                scores = res_item.get('rec_scores', [])
                polys = res_item.get('dt_polys', [])
                if len(polys) == 0:
                    polys = res_item.get('rec_polys', [])
                for i in range(min(len(texts), len(scores), len(polys))):
                    parsed_lines.append((polys[i], (texts[i], scores[i])))
            else:
                parsed_lines = res_item
                
            for line in parsed_lines:
                coords, (txt, conf) = line
                txt_clean = txt.strip()
                if not txt_clean:
                    continue
                    
                # Divide coords by 2 because we upscaled the image by 2x
                xs = [p[0] / 2.0 for p in coords]
                ys = [p[1] / 2.0 for p in coords]
                bx = max(0, int(min(xs)))
                by = max(0, int(min(ys)))
                bw = min(w - bx, int(max(xs) - min(xs)))
                bh = min(h - by, int(max(ys) - min(ys)))
                cx = bx + bw / 2.0
                cy = by + bh / 2.0

                boxes.append({
                    "text": txt_clean,
                    "confidence": round(float(conf), 4),
                    "x": bx,
                    "y": by,
                    "width": bw,
                    "height": bh,
                    "center_x": round(cx, 1),
                    "center_y": round(cy, 1),
                    "bbox": [bx, by, bx + bw, by + bh],
                    "norm_x": round(bx / w, 4),
                    "norm_y": round(by / h, 4),
                    "norm_w": round(bw / w, 4),
                    "norm_h": round(bh / h, 4),
                    "norm_cx": round(cx / w, 4),
                    "norm_cy": round(cy / h, 4)
                })
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "failed",
            "boxes": [],
            "text": "",
            "confidence": 0.0,
            "detected_side": "unknown",
            "error": f"PaddleOCR execution failed: {str(e)}",
            "engine": "paddleocr"
        }

    avg_conf = float(np.mean([b["confidence"] for b in boxes])) if boxes else 0.0
    full_text = " ".join(b["text"] for b in boxes).lower()
    
    detected_side = _detect_document_side_heuristic(img_bgr, full_text)

    result = {
        "status": "completed",
        "engine": "paddleocr",
        "confidence": round(avg_conf, 4),
        "boxes": boxes,
        "text": full_text,
        "detected_side": detected_side,
        "image_dimensions": {"width": w, "height": h}
    }
        
    return result
