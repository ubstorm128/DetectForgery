"""
OCR Bounding Box & Formatting Analysis
Extracts bounding boxes using Tesseract and analyzes geometric and formatting consistency.
"""
import pytesseract
from PIL import Image
import os
import math

def perform_ocr_analysis(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {"risk": 0, "status": "failed", "error": "File not found"}
        
    try:
        img = Image.open(image_path)
        # Use image_to_data to get bounding boxes
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:
        return {"risk": 0, "status": "failed", "error": str(e)}
        
    boxes = []
    n_boxes = len(data['text'])
    for i in range(n_boxes):
        if int(data['conf'][i]) > -1:  # Filter out empty/invalid blocks
            text = data['text'][i].strip()
            if text:
                boxes.append({
                    "text": text,
                    "confidence": float(data['conf'][i]),
                    "x": int(data['left'][i]),
                    "y": int(data['top'][i]),
                    "width": int(data['width'][i]),
                    "height": int(data['height'][i])
                })
                
    if not boxes:
        return {"risk": 0, "status": "completed", "confidence": 0, "anomalies": []}
        
    avg_conf = sum(b['confidence'] for b in boxes) / len(boxes)
    anomalies = []
    risk_score = 0
    
    # Simple formatting anomaly detection:
    # Look for characters/words that have an unusual height compared to the average.
    avg_height = sum(b['height'] for b in boxes) / len(boxes)
    
    for b in boxes:
        # If a word is 50% taller or shorter than average, flag it (could be pasting a different font size)
        if b['height'] > avg_height * 1.5 or b['height'] < avg_height * 0.5:
            anomalies.append(f"Unusual text height detected at '{b['text']}' (h:{b['height']}, avg:{avg_height:.1f})")
            risk_score += 15
            
    # Cap risk score
    risk_score = min(risk_score, 100)
    
    # Concatenate all text to detect side
    full_text = " ".join([b['text'] for b in boxes]).lower()
    
    # Side Detection Heuristics
    detected_side = "unknown"
    front_keywords = ["dob", "year of birth", "male", "female", "name"]
    back_keywords = ["address", "c/o", "s/o", "d/o", "w/o", "pincode", "uidai.gov.in", "1947"]
    
    front_score = sum(1 for kw in front_keywords if kw in full_text)
    back_score = sum(1 for kw in back_keywords if kw in full_text)
    
    if front_score > back_score:
        detected_side = "front"
    elif back_score > front_score:
        detected_side = "back"
        
    return {
        "status": "completed",
        "confidence": avg_conf,
        "risk": risk_score,
        "anomalies": anomalies[:5],  # Return up to 5 anomalies to avoid blowing up the payload
        "boxes": boxes,
        "text": full_text,
        "detected_side": detected_side
    }
