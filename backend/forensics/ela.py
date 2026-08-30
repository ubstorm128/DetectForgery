"""
Error Level Analysis (ELA)
Re-saves the image at a known JPEG quality and compares it to the original.
High variance in the difference image may indicate digital manipulation (e.g., pasting regions from other images).
"""
import cv2
import numpy as np
import os

def perform_ela(image_path: str, quality: int = 90) -> dict:
    if not os.path.exists(image_path):
        return {"risk": 0, "error": "File not found"}
        
    original = cv2.imread(image_path)
    if original is None:
        return {"risk": 0, "error": "Could not read image for ELA"}
        
    # Re-encode to JPEG
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    success, encoded = cv2.imencode('.jpg', original, encode_param)
    if not success:
        return {"risk": 0, "error": "Could not encode image"}
        
    recompressed = cv2.imdecode(encoded, 1)
    
    # Calculate absolute difference
    diff = cv2.absdiff(original, recompressed)
    
    avg_error = np.mean(diff)
    variance = np.var(diff)
    
    # Heuristic: naturally complex regions have high error, but local manipulation 
    # often creates very high variance in the difference.
    # Scale variance to a 0-100 risk score. (Tune divisor based on testing).
    risk_score = min(int(variance / 3.0), 100)
    
    return {
        "risk": risk_score,
        "avg_error": float(avg_error),
        "variance": float(variance)
    }
