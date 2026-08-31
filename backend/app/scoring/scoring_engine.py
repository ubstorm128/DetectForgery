"""
Risk & Authenticity Scoring Engine
Computes weighted authenticity score, separated image quality metrics,
and 3-tier risk classification (LOW RISK, MEDIUM RISK, HIGH RISK).
"""

WEIGHTS = {
    "ocr": 0.20,              # OCR / Text Consistency (20%)
    "layout": 0.20,           # Layout & Formatting (20%)
    "tampering": 0.25,        # Image Manipulation / ELA / Noise (25%)
    "copy_move": 0.10,        # Copy-Move Duplication (10%)
    "compression": 0.10,      # Compression Artifacts (10%)
    "metadata": 0.05,         # Metadata / EXIF (5%)
    "geometry": 0.10,         # Document Geometry / Resampling / Edges (10%)
}


def _invert_risk(risk_score: float) -> int:
    """Convert a 0-100 risk score into a 0-100 authenticity score."""
    return max(0, min(100, int(round(100 - risk_score))))


def calculate_overall_risk(
    results: dict,
    document_type: str = "aadhaar",
    image_quality_data: dict | None = None
) -> dict:
    """
    Computes weighted multi-factor authenticity score, risk level, confidence,
    and individual check breakdowns.
    """
    checks = {}

    # 1. OCR Consistency
    ocr_risk = results.get("ocr", {}).get("risk", 0)
    ocr_score = _invert_risk(ocr_risk)
    checks["ocr"] = {
        "score": ocr_score,
        "name": "OCR/Text Consistency",
        "weight": WEIGHTS["ocr"]
    }

    # 2. QR Analysis (if applicable)
    qr_data = results.get("qr", {})
    qr_risk = qr_data.get("risk")
    if qr_risk is not None:
        checks["qr"] = {
            "score": _invert_risk(qr_risk),
            "name": "QR Consistency",
            "detected": qr_data.get("detected", False)
        }

    # 3. Layout & Formatting
    layout_data = results.get("layout", {})
    layout_score = layout_data.get("score")
    if layout_score is not None:
        checks["layout"] = {
            "score": max(0, min(100, int(layout_score))),
            "name": "Layout & Formatting",
            "weight": WEIGHTS["layout"],
            "components": layout_data.get("components", {}),
            "explainable_reasons": layout_data.get("explainable_reasons", [])
        }
    else:
        checks["layout"] = {
            "score": 90,
            "name": "Layout & Formatting",
            "weight": WEIGHTS["layout"]
        }

    # 4. Image Manipulation (ELA + Noise)
    ela_risk = results.get("ela", {}).get("risk", 0)
    noise_risk = results.get("noise", {}).get("risk", 0)
    tamper_risk = (ela_risk * 0.6 + noise_risk * 0.4)
    checks["tampering"] = {
        "score": _invert_risk(tamper_risk),
        "name": "Image Manipulation",
        "weight": WEIGHTS["tampering"]
    }

    # 5. Copy-Move Analysis
    copy_move_data = results.get("copy_move", {})
    copy_risk = copy_move_data.get("risk", 0)
    copy_integrity = copy_move_data.get("integrity", _invert_risk(copy_risk))
    
    checks["copy_move"] = {
        "score": copy_integrity,
        "risk": copy_risk,
        "integrity": copy_integrity,
        "name": "Copy-Move Analysis",
        "weight": WEIGHTS["copy_move"]
    }

    # 6. Compression Analysis
    comp_risk = results.get("jpeg_dct", {}).get("risk", 0)
    checks["compression"] = {
        "score": _invert_risk(comp_risk),
        "name": "Compression Analysis",
        "weight": WEIGHTS["compression"]
    }

    # 7. Metadata Analysis
    meta_risk = results.get("metadata", {}).get("risk", 0)
    checks["metadata"] = {
        "score": _invert_risk(meta_risk),
        "name": "Metadata",
        "weight": WEIGHTS["metadata"]
    }

    # 8. Document Geometry / Edge Resampling
    edge_risk = results.get("resampling", {}).get("risk", 0)
    checks["geometry"] = {
        "score": _invert_risk(edge_risk),
        "name": "Document Geometry",
        "weight": WEIGHTS["geometry"]
    }

    # Assign check statuses (PASS / WARNING / FAIL)
    for check in checks.values():
        sc = check["score"]
        if sc >= 85:
            check["status"] = "PASS"
        elif sc >= 60:
            check["status"] = "WARNING"
        else:
            check["status"] = "FAIL"

    # Calculate weighted final authenticity score
    total_score = 0.0
    total_weight = 0.0

    for key, weight in WEIGHTS.items():
        if key in checks:
            total_score += checks[key]["score"] * weight
            total_weight += weight

    if total_weight > 0:
        final_authenticity_score = int(round(total_score / total_weight))
    else:
        final_authenticity_score = 85

    final_authenticity_score = max(0, min(100, final_authenticity_score))
    risk_score = 100 - final_authenticity_score

    # 3-Tier Classification
    major_layout_mismatch = layout_data.get("major_layout_mismatch", False)
    
    if major_layout_mismatch:
        risk_level = "HIGH RISK"
        classification = "LIKELY_FAKE"
        final_authenticity_score = min(final_authenticity_score, 20) # Cap score at 20
        risk_score = 100 - final_authenticity_score
    elif final_authenticity_score >= 80:
        risk_level = "LOW RISK"
        classification = "GENUINE"
    elif final_authenticity_score >= 65:
        risk_level = "MEDIUM RISK"
        classification = "SUSPICIOUS"
    else:
        risk_level = "HIGH RISK"
        classification = "LIKELY_FAKE"

    # Compute overall analysis confidence
    ocr_conf = results.get("ocr", {}).get("confidence", 0.90)
    quality_score = image_quality_data.get("score", 85) if image_quality_data else 85
    # Overall confidence is influenced by OCR clarity and image quality
    confidence = round(float(min(1.0, max(0.4, (ocr_conf * 0.6 + (quality_score / 100.0) * 0.4)))), 2)

    # Suspicious regions for visual overlay
    suspicious_regions = []
    if ocr_risk > 50:
        suspicious_regions.append({
            "type": "text",
            "reason": "OCR character/text inconsistency detected",
            "confidence": 0.85
        })

    if tamper_risk > 40:
        suspicious_regions.append({
            "type": "image",
            "reason": "Digital tampering artifacts or irregular noise detected",
            "confidence": 0.88
        })

    if checks["layout"]["score"] < 70:
        suspicious_regions.append({
            "type": "layout",
            "reason": "Structural layout offsets detected against expected template",
            "confidence": 0.85
        })

    warnings = []
    if layout_data.get("anomalies"):
        warnings.extend(layout_data["anomalies"])
    if image_quality_data and image_quality_data.get("warnings"):
        warnings.extend(image_quality_data["warnings"])

    return {
        "document_type": document_type,
        "overall_score": final_authenticity_score,
        "authenticity_score": final_authenticity_score,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "result": classification,
        "confidence": confidence,
        "checks": checks,
        "image_quality": image_quality_data or {"score": 88},
        "suspicious_regions": suspicious_regions,
        "warnings": warnings,
        "disclaimer": "Automated forensic assessment based on structural evidence. Not definitive legal proof of document authenticity."
    }