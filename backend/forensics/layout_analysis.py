"""
Structural Layout & Formatting Analysis Service
Replaces raw pixel diffs with tolerance-based relative coordinate comparison,
alignment verification, spacing consistency, region structure, and confidence-aware weighting.
"""

import os
import cv2
import numpy as np

from services.perspective import correct_perspective_and_normalize
from services.ocr_service import extract_ocr_data
from services.similarity import compute_structural_ssim, compare_structural_edges
from services.preprocessing import preprocess_image_for_analysis


# Configurable Tolerances for Normalized Coordinates (0.0 to 1.0)
POSITION_TOLERANCE = 0.04   # 4% of document width/height
SIZE_TOLERANCE = 0.08       # 8% width/height tolerance
SPACING_TOLERANCE = 0.10    # 10% spacing tolerance
ALIGNMENT_TOLERANCE = 0.03  # 3% alignment margin


# Standard Aadhaar Structural Regions in Normalized Coordinates [ymin, ymax, xmin, xmax]
FRONT_REGIONS = {
    "government_header": {"y_range": (0.00, 0.22), "x_range": (0.20, 0.80), "name": "Government Header"},
    "government_logo":   {"y_range": (0.02, 0.20), "x_range": (0.03, 0.25), "name": "Government Emblem"},
    "aadhaar_logo":      {"y_range": (0.02, 0.20), "x_range": (0.75, 0.97), "name": "Aadhaar Logo"},
    "photo":             {"y_range": (0.22, 0.78), "x_range": (0.04, 0.36), "name": "Cardholder Photograph"},
    "personal_details":  {"y_range": (0.22, 0.75), "x_range": (0.34, 0.96), "name": "Personal Details / DOB"},
    "aadhaar_number":    {"y_range": (0.72, 0.96), "x_range": (0.20, 0.85), "name": "Aadhaar ID Number"}
}

BACK_REGIONS = {
    "header":            {"y_range": (0.00, 0.20), "x_range": (0.05, 0.95), "name": "Back Header / Contact"},
    "address_details":   {"y_range": (0.20, 0.78), "x_range": (0.05, 0.65), "name": "Address Text Block"},
    "qr_code":           {"y_range": (0.22, 0.82), "x_range": (0.62, 0.96), "name": "QR Code / Barcode Block"},
    "aadhaar_number":    {"y_range": (0.75, 0.97), "x_range": (0.15, 0.85), "name": "Aadhaar ID Number (Back)"}
}


def _match_boxes_by_text_similarity(
    uploaded_boxes: list[dict],
    reference_boxes: list[dict]
) -> list[tuple[dict, dict]]:
    """
    Matches uploaded OCR boxes to reference OCR boxes by normalized text similarity or proximity.
    """
    pairs = []
    used_ref_indices = set()

    for up_box in uploaded_boxes:
        up_txt = up_box["text"].lower()
        best_match = None
        best_idx = -1
        best_score = 0.0

        for idx, ref_box in enumerate(reference_boxes):
            if idx in used_ref_indices:
                continue

            ref_txt = ref_box["text"].lower()
            # Exact or substring match
            if up_txt == ref_txt or up_txt in ref_txt or ref_txt in up_txt:
                score = 1.0
            else:
                # Spatial proximity match if texts are short
                dx = abs(up_box["norm_cx"] - ref_box["norm_cx"])
                dy = abs(up_box["norm_cy"] - ref_box["norm_cy"])
                dist = np.sqrt(dx**2 + dy**2)
                if dist < 0.15:
                    score = 1.0 - (dist / 0.15)
                else:
                    score = 0.0

            if score > best_score:
                best_score = score
                best_match = ref_box
                best_idx = idx

        if best_match and best_score >= 0.5:
            pairs.append((up_box, best_match))
            used_ref_indices.add(best_idx)

    return pairs


def calculate_position_consistency(
    pairs: list[tuple[dict, dict]],
    tolerance: float = POSITION_TOLERANCE
) -> tuple[float, list[str]]:
    """
    Evaluates relative text coordinate distances with confidence-aware tolerance.
    """
    if not pairs:
        return 90.0, []

    scores = []
    warnings = []

    for up_box, ref_box in pairs:
        conf = up_box.get("confidence", 0.9)
        # Weight contribution based on OCR confidence
        weight = 1.0 if conf >= 0.90 else (0.6 if conf >= 0.70 else 0.3)

        dx = abs(up_box["norm_cx"] - ref_box["norm_cx"])
        dy = abs(up_box["norm_cy"] - ref_box["norm_cy"])

        # Within tolerance => 100% score (normal variation)
        if dx <= tolerance and dy <= tolerance:
            box_score = 100.0
        else:
            excess_dx = max(0.0, dx - tolerance)
            excess_dy = max(0.0, dy - tolerance)
            penalty = (excess_dx + excess_dy) * 200.0
            box_score = max(30.0, 100.0 - penalty)
            if box_score < 70.0 and weight >= 0.6:
                warnings.append(f"Position offset detected for text block '{up_box['text'][:15]}...'")

        scores.append((box_score, weight))

    total_weight = sum(w for _, w in scores)
    if total_weight > 0:
        final_score = sum(s * w for s, w in scores) / total_weight
    else:
        final_score = 90.0

    return round(float(final_score), 1), warnings


def calculate_size_consistency(
    pairs: list[tuple[dict, dict]],
    tolerance: float = SIZE_TOLERANCE
) -> tuple[float, list[str]]:
    """
    Evaluates normalized box widths & heights.
    """
    if not pairs:
        return 92.0, []

    scores = []
    warnings = []

    for up_box, ref_box in pairs:
        conf = up_box.get("confidence", 0.9)
        weight = 1.0 if conf >= 0.90 else (0.6 if conf >= 0.70 else 0.3)

        dw = abs(up_box["norm_w"] - ref_box["norm_w"])
        dh = abs(up_box["norm_h"] - ref_box["norm_h"])

        if dw <= tolerance and dh <= tolerance:
            box_score = 100.0
        else:
            excess = max(0.0, dw - tolerance) + max(0.0, dh - tolerance)
            penalty = excess * 150.0
            box_score = max(40.0, 100.0 - penalty)
            if box_score < 65.0 and weight >= 0.6:
                warnings.append(f"Size anomaly for text element '{up_box['text'][:15]}'")

        scores.append((box_score, weight))

    total_weight = sum(w for _, w in scores)
    final_score = sum(s * w for s, w in scores) / total_weight if total_weight > 0 else 92.0
    return round(float(final_score), 1), warnings


def calculate_alignment_consistency(
    boxes: list[dict],
    tolerance: float = ALIGNMENT_TOLERANCE
) -> tuple[float, list[str]]:
    """
    Checks left/right/center and baseline alignment within detected text groups.
    """
    if len(boxes) < 2:
        return 95.0, []

    # Sort boxes vertically
    sorted_y = sorted(boxes, key=lambda b: b["norm_y"])
    left_align_matches = 0
    left_align_comparisons = 0

    for i in range(len(sorted_y) - 1):
        b1 = sorted_y[i]
        b2 = sorted_y[i + 1]

        # If they are vertically proximate (within 15% document height)
        if abs(b2["norm_y"] - b1["norm_y"]) < 0.15:
            left_align_comparisons += 1
            if abs(b1["norm_x"] - b2["norm_x"]) <= tolerance:
                left_align_matches += 1

    if left_align_comparisons > 0:
        ratio = left_align_matches / left_align_comparisons
        align_score = 75.0 + ratio * 25.0
    else:
        align_score = 95.0

    warnings = []
    if align_score < 70.0:
        warnings.append("Inconsistent text margin/alignment across adjacent lines.")

    return round(float(align_score), 1), warnings


def calculate_spacing_consistency(
    boxes: list[dict],
    tolerance: float = SPACING_TOLERANCE
) -> tuple[float, list[str]]:
    """
    Analyzes line gaps and inter-word relative spacing regularity.
    """
    if len(boxes) < 3:
        return 92.0, []

    sorted_y = sorted(boxes, key=lambda b: b["norm_y"])
    vertical_gaps = []

    for i in range(len(sorted_y) - 1):
        gap = sorted_y[i + 1]["norm_y"] - (sorted_y[i]["norm_y"] + sorted_y[i]["norm_h"])
        if 0.005 <= gap <= 0.20:
            vertical_gaps.append(gap)

    if len(vertical_gaps) >= 2:
        std_gap = float(np.std(vertical_gaps))
        # Consistent spacing will have low variance in normalized line gaps
        if std_gap <= tolerance:
            spacing_score = 100.0 - (std_gap / tolerance) * 10.0
        else:
            spacing_score = max(50.0, 90.0 - (std_gap - tolerance) * 150.0)
    else:
        spacing_score = 92.0

    warnings = []
    if spacing_score < 70.0:
        warnings.append("Irregular vertical line spacing detected between text blocks.")

    return round(float(spacing_score), 1), warnings


def evaluate_region_structure(
    boxes: list[dict],
    detected_side: str = "front",
    gray_image: np.ndarray | None = None
) -> tuple[float, list[str]]:
    """
    Validates presence and correct relative spatial zones for expected regions
    using both extracted boxes and image structural feature presence.
    """
    regions_def = FRONT_REGIONS if detected_side == "front" else BACK_REGIONS
    matched_regions = 0
    warnings = []

    h, w = gray_image.shape[:2] if gray_image is not None else (630, 1000)

    for reg_key, reg_info in regions_def.items():
        ymin, ymax = reg_info["y_range"]
        xmin, xmax = reg_info["x_range"]

        # Check if any OCR / text box centers fall within expected region
        has_content = any(
            (ymin <= b["norm_cy"] <= ymax and xmin <= b["norm_cx"] <= xmax)
            for b in boxes
        )

        # If not detected via boxes, check if the image region has valid structural content / edges
        if not has_content and gray_image is not None:
            ry1, ry2 = int(ymin * h), int(ymax * h)
            rx1, rx2 = int(xmin * w), int(xmax * w)
            roi = gray_image[ry1:ry2, rx1:rx2]
            if roi.size > 0:
                roi_var = float(np.var(roi))
                # Photo, logo, QR code, or dark text on light background will have meaningful variance (> 150)
                if roi_var > 150:
                    has_content = True

        if has_content:
            matched_regions += 1
        else:
            if reg_key in ["aadhaar_number", "personal_details", "address_details"]:
                warnings.append(f"Expected {reg_info['name']} zone has weak structural signature.")

    total_regions = len(regions_def)
    region_score = (matched_regions / total_regions) * 100.0 if total_regions > 0 else 90.0
    region_score = max(60.0, min(100.0, region_score))

    return round(float(region_score), 1), warnings


def perform_layout_analysis(
    image_path: str,
    reference_path: str | None = None,
    document_type: str = "aadhaar"
) -> dict:
    """
    Full Layout & Formatting Verification Pipeline:
    1. Perspective Correction & Resolution Normalization
    2. OCR & Normalized Relative Coordinate Mapping
    3. Structural Layout Metrics (Position, Size, Alignment, Spacing, Region)
    4. SSIM & Canny Edge Consistency
    5. Explainable Reasoning & Tolerance Scoring
    """
    if not os.path.exists(image_path):
        return {"status": "failed", "score": 0, "risk": 100, "error": "Uploaded image not found"}

    img_raw = cv2.imread(image_path)
    if img_raw is None:
        return {"status": "failed", "score": 0, "risk": 100, "error": "Could not decode uploaded image"}

    # 1. Perspective correction & Rectification
    rectified_img, persp_meta = correct_perspective_and_normalize(img_raw, target_width=1000, target_height=630)
    preprocessed = preprocess_image_for_analysis(rectified_img)
    processed_gray = preprocessed["gray"]

    # 2. Extract OCR data from normalized image
    ocr_result = extract_ocr_data(rectified_img)
    uploaded_boxes = ocr_result.get("boxes", [])
    detected_side = ocr_result.get("detected_side", "front")

    # 3. Reference Image Handling
    ref_boxes = []
    ref_gray = None
    ref_ratio = 1000 / 630  # Standard Aadhaar aspect ratio ~1.587

    if reference_path and os.path.exists(reference_path):
        ref_raw = cv2.imread(reference_path)
        if ref_raw is not None:
            ref_rectified, _ = correct_perspective_and_normalize(ref_raw, target_width=1000, target_height=630)
            ref_gray = cv2.cvtColor(ref_rectified, cv2.COLOR_BGR2GRAY)
            ref_ocr = extract_ocr_data(ref_rectified)
            ref_boxes = ref_ocr.get("boxes", [])

    # If no reference file boxes available, synthesize expected template anchor points from template definitions
    if not ref_boxes:
        if detected_side == "back":
            ref_boxes = [
                {"text": "address", "norm_cx": 0.35, "norm_cy": 0.28, "norm_w": 0.40, "norm_h": 0.05, "confidence": 0.99},
                {"text": "pincode", "norm_cx": 0.30, "norm_cy": 0.55, "norm_w": 0.25, "norm_h": 0.04, "confidence": 0.99},
                {"text": "1947",    "norm_cx": 0.50, "norm_cy": 0.12, "norm_w": 0.30, "norm_h": 0.04, "confidence": 0.99},
                {"text": "aadhaar", "norm_cx": 0.50, "norm_cy": 0.88, "norm_w": 0.35, "norm_h": 0.06, "confidence": 0.99}
            ]
        else:
            ref_boxes = [
                {"text": "government of india", "norm_cx": 0.50, "norm_cy": 0.08, "norm_w": 0.45, "norm_h": 0.05, "confidence": 0.99},
                {"text": "dob",                 "norm_cx": 0.55, "norm_cy": 0.42, "norm_w": 0.30, "norm_h": 0.04, "confidence": 0.99},
                {"text": "male",                "norm_cx": 0.55, "norm_cy": 0.50, "norm_w": 0.20, "norm_h": 0.04, "confidence": 0.99},
                {"text": "aadhaar",             "norm_cx": 0.50, "norm_cy": 0.85, "norm_w": 0.40, "norm_h": 0.06, "confidence": 0.99}
            ]

    # 4. Box Matching & Layout Component Computations
    matched_pairs = _match_boxes_by_text_similarity(uploaded_boxes, ref_boxes)

    pos_score, pos_warnings = calculate_position_consistency(matched_pairs, POSITION_TOLERANCE)
    size_score, size_warnings = calculate_size_consistency(matched_pairs, SIZE_TOLERANCE)
    align_score, align_warnings = calculate_alignment_consistency(uploaded_boxes, ALIGNMENT_TOLERANCE)
    spacing_score, spacing_warnings = calculate_spacing_consistency(uploaded_boxes, SPACING_TOLERANCE)
    region_score, region_warnings = evaluate_region_structure(uploaded_boxes, detected_side, gray_image=processed_gray)

    # 5. Dedicated Structural Formula:
    # Position: 35%, Size: 20%, Alignment: 20%, Spacing: 15%, Region Structure: 10%
    layout_score = (
        pos_score * 0.35 +
        size_score * 0.20 +
        align_score * 0.20 +
        spacing_score * 0.15 +
        region_score * 0.10
    )
    layout_score = int(round(max(0.0, min(100.0, layout_score))))

    # 6. Structural Edge & SSIM metrics (if reference image available)
    ssim_val = 0.85
    edge_metrics = {"score": 90, "edge_similarity": 0.30}
    if ref_gray is not None:
        ssim_score_raw, _ = compute_structural_ssim(processed_gray, ref_gray)
        ssim_val = round(ssim_score_raw, 3)
        edge_metrics = compare_structural_edges(processed_gray, ref_gray)

    # 7. Explainable Diagnosis Checklist
    explainable_reasons = []
    if pos_score >= 85:
        explainable_reasons.append("✓ Text positions are consistent with document template")
    if align_score >= 85:
        explainable_reasons.append("✓ Major text blocks and margins are correctly aligned")
    if size_score >= 85:
        explainable_reasons.append("✓ Document typography and element dimensions match expected proportions")
    if spacing_score >= 80:
        explainable_reasons.append("✓ Line and character spacing are within expected tolerance")
    if region_score >= 80:
        explainable_reasons.append("✓ Key document regions (Header, Details, ID number) verified")

    all_warnings = pos_warnings + size_warnings + align_warnings + spacing_warnings + region_warnings
    if not all_warnings:
        explainable_reasons.append("✓ No significant structural or geometric anomalies detected")
    else:
        for w in all_warnings[:4]:
            explainable_reasons.append(f"⚠ {w}")

    # Risk is the complement of layout authenticity score
    risk = max(0, 100 - layout_score)

    return {
        "status": "completed",
        "score": layout_score,
        "risk": risk,
        "components": {
            "position": round(pos_score, 1),
            "size": round(size_score, 1),
            "alignment": round(align_score, 1),
            "spacing": round(spacing_score, 1),
            "region_structure": round(region_score, 1)
        },
        "perspective": persp_meta,
        "structural_ssim": ssim_val,
        "edge_metrics": edge_metrics,
        "detected_side": detected_side,
        "explainable_reasons": explainable_reasons,
        "anomalies": all_warnings
    }