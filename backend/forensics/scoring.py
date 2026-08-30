"""
Risk Scoring System
Aggregates available forensic checks.

Checks that are not implemented yet are excluded from scoring.
"""

WEIGHTS = {
    "ocr": 0.20,
    "qr": 0.10,
    "layout": 0.15,
    "tampering": 0.15,
    "compression": 0.05,
    "metadata": 0.05,
}


def _invert_risk(risk_score: float) -> int:
    """Convert a 0-100 risk score into a 0-100 authenticity score."""
    return max(0, min(100, int(round(100 - risk_score))))


def calculate_overall_risk(
    results: dict,
    document_type: str = "unknown"
) -> dict:

    checks = {}

    # ---------------------------------------------------------
    # 1. OCR
    # ---------------------------------------------------------

    ocr_risk = results.get("ocr", {}).get("risk", 0)

    checks["ocr"] = {
        "score": _invert_risk(ocr_risk)
    }

    # ---------------------------------------------------------
    # 2. QR Analysis
    # ---------------------------------------------------------

    qr_risk = results.get("qr", {}).get("risk")
    if qr_risk is not None:
        checks["qr"] = {
            "score": _invert_risk(qr_risk)
        }

    # ---------------------------------------------------------
    # 3. Reference-based Layout
    # ---------------------------------------------------------

    layout_score = results.get("layout", {}).get("score")

    if layout_score is not None:
        checks["layout"] = {
            "score": max(
                0,
                min(100, int(layout_score))
            )
        }

    # ---------------------------------------------------------
    # 3. Tampering
    # ---------------------------------------------------------

    ela_risk = results.get("ela", {}).get("risk", 0)
    noise_risk = results.get("noise", {}).get("risk", 0)
    copy_risk = results.get("copy_move", {}).get("risk", 0)
    edge_risk = results.get("resampling", {}).get("risk", 0)

    avg_tamper_risk = (
        ela_risk +
        noise_risk +
        copy_risk +
        edge_risk
    ) / 4

    checks["tampering"] = {
        "score": _invert_risk(avg_tamper_risk)
    }

    # ---------------------------------------------------------
    # 4. Compression
    # ---------------------------------------------------------

    comp_risk = results.get(
        "jpeg_dct", {}
    ).get("risk", 0)

    checks["compression"] = {
        "score": _invert_risk(comp_risk)
    }

    # ---------------------------------------------------------
    # 5. Metadata
    # ---------------------------------------------------------

    meta_risk = results.get(
        "metadata", {}
    ).get("risk", 0)

    checks["metadata"] = {
        "score": _invert_risk(meta_risk)
    }

    # ---------------------------------------------------------
    # Assign check statuses
    # ---------------------------------------------------------

    for check in checks.values():

        score = check["score"]

        if score >= 85:
            check["status"] = "PASS"

        elif score >= 60:
            check["status"] = "WARNING"

        else:
            check["status"] = "FAIL"

    # ---------------------------------------------------------
    # Calculate normalized weighted score
    # ---------------------------------------------------------

    total_weight = 0.0
    total_score = 0.0

    for key, weight in WEIGHTS.items():

        if key in checks:

            total_score += (
                checks[key]["score"] * weight
            )

            total_weight += weight

    if total_weight > 0:
        final_score = int(
            round(total_score / total_weight)
        )
    else:
        final_score = 0

    # ---------------------------------------------------------
    # Classification
    # ---------------------------------------------------------

    if final_score >= 85:
        classification = "GENUINE"

    elif final_score >= 60:
        classification = "SUSPICIOUS"

    else:
        classification = "LIKELY_FAKE"

    # ---------------------------------------------------------
    # Suspicious regions
    # ---------------------------------------------------------

    suspicious_regions = []

    if ocr_risk > 50:

        suspicious_regions.append({
            "type": "text",
            "reason": "OCR-related anomalies detected",
            "confidence": 0.85
        })

    if avg_tamper_risk > 40:

        suspicious_regions.append({
            "type": "image",
            "reason": "Digital tampering artifacts detected",
            "confidence": 0.90
        })

    # Layout anomalies
    if (
        "layout" in checks
        and checks["layout"]["score"] < 60
    ):

        suspicious_regions.append({
            "type": "layout",
            "reason": "Document layout differs significantly from reference.",
            "confidence": 0.85
        })

    return {
        "document_type": document_type,
        "result": classification,
        "authenticity_score": final_score,
        "checks": checks,
        "suspicious_regions": suspicious_regions
    }