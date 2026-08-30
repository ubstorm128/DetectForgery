"""
Risk Scoring System
Aggregates risk scores from various forensic modules.
"""

# Configurable weights for Authenticity Score (sum to 1.0)
WEIGHTS = {
    "ocr": 0.20,
    "qr": 0.25,
    "layout": 0.15,
    "font_consistency": 0.10,
    "tampering": 0.15,
    "compression": 0.05,
    "metadata": 0.05,
    "photo_analysis": 0.05
}

def _invert_risk(risk_score: int) -> int:
    """Converts a 0-100 Risk score to a 0-100 Authenticity score."""
    return max(0, min(100, 100 - risk_score))

def calculate_overall_risk(results: dict, document_type: str = "unknown") -> dict:
    """
    Calculates weighted Authenticity Score. Returns a full JSON-ready dictionary.
    """
    checks = {}
    
    # 1. OCR (20%)
    ocr_risk = results.get("ocr", {}).get("risk", 0)
    checks["ocr"] = {"score": _invert_risk(ocr_risk)}
    
    # 2. QR (25%) - Mocked as pass for now
    checks["qr"] = {"score": 100}
    
    # 3. Layout (15%) - Mocked as pass for now
    checks["layout"] = {"score": 100}
    
    # 4. Font Consistency (10%) - Derived from OCR or mocked
    checks["font_consistency"] = {"score": _invert_risk(ocr_risk // 2)}
    
    # 5. Tampering (15%) - Combine ELA, Noise, CopyMove, Resampling
    ela_risk = results.get("ela", {}).get("risk", 0)
    noise_risk = results.get("noise", {}).get("risk", 0)
    copy_risk = results.get("copy_move", {}).get("risk", 0)
    edge_risk = results.get("resampling", {}).get("risk", 0)
    avg_tamper_risk = (ela_risk + noise_risk + copy_risk + edge_risk) / 4
    checks["tampering"] = {"score": _invert_risk(int(avg_tamper_risk))}
    
    # 6. Compression (5%)
    comp_risk = results.get("jpeg_dct", {}).get("risk", 0)
    checks["compression"] = {"score": _invert_risk(comp_risk)}
    
    # 7. Metadata (5%)
    meta_risk = results.get("metadata", {}).get("risk", 0)
    checks["metadata"] = {"score": _invert_risk(meta_risk)}
    
    # 8. Photo Analysis (5%) - Mocked for now
    checks["photo_analysis"] = {"score": 100}
    
    # Calculate Total Authenticity Score
    total_score = 0.0
    for key, weight in WEIGHTS.items():
        score = checks[key]["score"]
        total_score += score * weight
        
        # Assign status based on score
        if score >= 85:
            checks[key]["status"] = "PASS"
        elif score >= 60:
            checks[key]["status"] = "WARNING"
        else:
            checks[key]["status"] = "FAIL"
            
    final_score = int(round(total_score))
    
    # Classify overall result
    if final_score >= 85:
        classification = "GENUINE"
    elif final_score >= 60:
        classification = "SUSPICIOUS"
    else:
        classification = "LIKELY_FAKE"
        
    # Aggregate suspicious regions
    suspicious_regions = []
    if ocr_risk > 50:
        suspicious_regions.append({"type": "text", "reason": "Formatting or text anomalies detected", "confidence": 0.85})
    if avg_tamper_risk > 40:
        suspicious_regions.append({"type": "image", "reason": "Digital tampering artifacts detected (ELA/Noise/Cloning)", "confidence": 0.90})
        
    return {
        "document_type": document_type,
        "result": classification,
        "authenticity_score": final_score,
        "checks": checks,
        "suspicious_regions": suspicious_regions
    }
