import cv2
import numpy as np
from card_detectors.aadhaar.detector import AadhaarDetector
from card_detectors.pan.detector import PANDetector

def detect_supported_card(image_path: str, document_type: str, ocr_data: dict, threshold: float = 0.45) -> dict:
    """
    Multi-factor card detection to ensure genuine cards are not rejected due to OCR failure on card number alone.
    Evaluates: Aspect Ratio, Text Density, Card Keywords, and Exact Number Detection.
    Returns: {"detected": bool, "confidence": float, "debug_log": list}
    """
    debug_log = []
    score = 0.0
    
    img = cv2.imread(image_path)
    if img is None:
        return {"detected": False, "confidence": 0.0, "debug_log": ["Failed to load image"]}
    
    h, w = img.shape[:2]
    
    # 1. Aspect Ratio Check (Now always ~1.58 due to prior cropping, so we verify but give less weight)
    if min(h, w) > 0:
        aspect_ratio = max(h, w) / min(h, w)
        if 1.4 <= aspect_ratio <= 1.8:
            score += 0.1
            debug_log.append(f"Pass: Aspect ratio {aspect_ratio:.2f} is card-like (+0.1)")
        else:
            debug_log.append(f"Fail: Aspect ratio {aspect_ratio:.2f} is not typical for ID cards (+0.0)")
    else:
        debug_log.append("Fail: Invalid image dimensions (+0.0)")
        
    # 2. Text Density & Structure
    boxes = ocr_data.get("boxes", [])
    if len(boxes) >= 8:
        score += 0.2
        debug_log.append(f"Pass: Found {len(boxes)} text boxes, strong document structure (+0.2)")
    elif len(boxes) >= 4:
        score += 0.1
        debug_log.append(f"Partial Pass: Found {len(boxes)} text boxes (+0.1)")
    else:
        debug_log.append(f"Fail: Insufficient text boxes detected ({len(boxes)}) (+0.0)")
        
    # 3. Card-specific keywords
    full_text = ocr_data.get("text", "").lower()
    
    if document_type.lower() == "aadhaar":
        keywords = ["government of india", "dob", "year of birth", "male", "female", "address", "father", "uidai", "mera aadhaar", "1947", "helpdesk", "enrolment", "identity"]
        detector = AadhaarDetector()
    elif document_type.lower() == "pan":
        keywords = ["income tax department", "permanent account number", "name", "father's name", "signature", "govt. of india"]
        detector = PANDetector()
    else:
        keywords = []
        detector = None
        
    matched_keywords = sum(1 for kw in keywords if kw in full_text)
    if matched_keywords >= 2:
        # Cap keyword score at 0.3 (3+ keywords)
        kw_score = min(0.3, matched_keywords * 0.1)
        score += kw_score
        debug_log.append(f"Pass: Found {matched_keywords} '{document_type}' keyword(s) (+{kw_score:.2f})")
    else:
        debug_log.append(f"Fail: Insufficient '{document_type}' specific keywords found (+0.0)")
        
    # 4. Strict Regex Card Number detection (Crucial for validation)
    if detector:
        card_check = detector.detect_card_number(boxes, ocr_data.get("text", ""))
        if card_check.get("detected"):
            score += 0.6  # Highly weighted
            debug_log.append(f"Pass: Exact {document_type} number pattern detected confidently (+0.6)")
        else:
            debug_log.append(f"Fail: Exact card number NOT detected cleanly by strict regex (+0.0)")
            
    # 5. Structural / Visual Features (QR Code & Photo Region)
    # Detect QR Code (typically on the back of Aadhaar/PAN)
    try:
        qr_detector = cv2.QRCodeDetector()
        _, points, _ = qr_detector.detectAndDecode(img)
        if points is not None and len(points) > 0:
            score += 0.25
            debug_log.append("Pass: QR Code detected (+0.25)")
    except Exception:
        pass
        
    # Detect high variance regions (Photo on left, or QR/Barcode on right)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    if h > 0 and w > 0:
        left_roi = gray[int(h * 0.25):int(h * 0.75), int(w * 0.05):int(w * 0.35)]
        right_roi = gray[int(h * 0.25):int(h * 0.75), int(w * 0.65):int(w * 0.95)]
        left_var = float(np.var(left_roi)) if left_roi.size > 0 else 0
        right_var = float(np.var(right_roi)) if right_roi.size > 0 else 0
        
        if left_var > 400 and left_var > right_var * 1.1:
            score += 0.15
            debug_log.append(f"Pass: High variance on left side (likely photo region) ({left_var:.0f} > 400) (+0.15)")
        elif right_var > 600 and right_var > left_var:
            score += 0.15
            debug_log.append(f"Pass: High variance on right side (likely QR/Barcode) ({right_var:.0f} > 600) (+0.15)")
        else:
            debug_log.append("Fail: No typical ID card regional variance found (+0.0)")

    # Normalize score
    final_score = min(1.0, score)
    debug_log.append(f"Final card detection confidence score: {final_score:.2f}")
    
    detected = final_score >= threshold
    
    if detected:
        debug_log.append(f"Result: ACCEPTED (Score >= {threshold})")
    else:
        debug_log.append(f"Result: REJECTED (Score < {threshold})")
        
    return {
        "detected": detected,
        "confidence": final_score,
        "debug_log": debug_log
    }
