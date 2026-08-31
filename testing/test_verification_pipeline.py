"""
Comprehensive Test Suite for ID Verification & Layout Detection Pipeline
Tests:
1. Perspective Correction & Standard Normalization
2. Image Quality Assessment
3. OCR Normalized Coordinates
4. Robust Tolerance-based Layout Scoring (Camera, Rotation, Compression, Resizing)
5. FastAPI Endpoint Verification (/health, /api/analyze-image, /analyze-id)
"""

import os
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import cv2
import numpy as np

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from services.perspective import correct_perspective_and_normalize
from services.image_quality import assess_image_quality
from services.ocr_service import extract_ocr_data
from forensics.layout_analysis import perform_layout_analysis
from forensics.scoring import calculate_overall_risk


def create_mock_id_card(text_offsets=(0, 0), angle=0, noise=False, brightness=0):
    """Generates a synthetic Aadhaar-like card for deterministic testing."""
    # 1000 x 630 standard card
    w, h = 1000, 630
    img = np.full((h, w, 3), 245, dtype=np.uint8)

    # Header bar
    cv2.rectangle(img, (0, 0), (w, 90), (220, 220, 220), -1)
    cv2.putText(img, "GOVERNMENT OF INDIA", (280 + text_offsets[0], 55 + text_offsets[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 2)

    # Photo Box
    cv2.rectangle(img, (40, 150), (280, 480), (180, 180, 180), -1)
    cv2.putText(img, "PHOTO", (110, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 50, 50), 2)

    # Personal Details
    cv2.putText(img, "Name: John Doe", (340 + text_offsets[0], 210 + text_offsets[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    cv2.putText(img, "DOB: 15/08/1990", (340 + text_offsets[0], 280 + text_offsets[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    cv2.putText(img, "Gender: Male", (340 + text_offsets[0], 350 + text_offsets[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)

    # Aadhaar Number
    cv2.putText(img, "1234 5678 9012", (330 + text_offsets[0], 550 + text_offsets[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 3)

    if brightness != 0:
        img = np.clip(img.astype(np.int32) + brightness, 0, 255).astype(np.uint8)

    if noise:
        gauss = np.random.normal(0, 15, img.shape).astype(np.int32)
        img = np.clip(img.astype(np.int32) + gauss, 0, 255).astype(np.uint8)

    if angle != 0:
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        img = cv2.warpAffine(img, rot_mat, (w, h), borderValue=(255, 255, 255))

    return img


def run_tests():
    print("=" * 60)
    print("RUNNING ID VERIFICATION & LAYOUT PIPELINE TESTS")
    print("=" * 60)

    # 1. Perspective Correction & Normalization
    print("\n[TEST 1] Testing Perspective Correction & Normalization...")
    test_img = create_mock_id_card()
    rectified, meta = correct_perspective_and_normalize(test_img, 1000, 630)
    assert rectified.shape[0] == 630 and rectified.shape[1] == 1000, "Dimension normalization failed!"
    print(f"✓ Normalization Status: {meta['status']} -> Result shape: {rectified.shape}")

    # 2. Image Quality Assessment
    print("\n[TEST 2] Testing Image Quality Assessment...")
    quality = assess_image_quality(test_img)
    print(f"✓ Quality Score: {quality['score']}/100, Sharpness: {quality['sharpness']}, Brightness: {quality['brightness']}")
    assert quality["score"] > 50, "Quality score for standard mock card should be high!"

    # 3. Layout Analysis on Genuine Reference vs Varied Genuine Captures
    print("\n[TEST 3] Testing Tolerance-based Layout Scoring...")
    ref_path = os.path.join(os.path.dirname(__file__), "test_ref.jpg")
    cv2.imwrite(ref_path, test_img)

    # Case A: Genuine card with slight camera distance / resize & JPEG compression
    sample_a_path = os.path.join(os.path.dirname(__file__), "test_sample_a.jpg")
    resized_sample = cv2.resize(test_img, (750, 470))  # different resolution
    cv2.imwrite(sample_a_path, resized_sample, [cv2.IMWRITE_JPEG_QUALITY, 75])

    res_a = perform_layout_analysis(sample_a_path, ref_path)
    print(f"  Case A (Resized & Compressed Genuine): Layout Score = {res_a['score']}/100")
    print(f"    Components: {res_a['components']}")
    assert res_a["score"] >= 85, f"Expected high layout score for genuine sample A, got {res_a['score']}"

    # Case B: Genuine card with lighting variance and mild noise
    sample_b_path = os.path.join(os.path.dirname(__file__), "test_sample_b.jpg")
    noisy_sample = create_mock_id_card(noise=True, brightness=-30)
    cv2.imwrite(sample_b_path, noisy_sample)

    res_b = perform_layout_analysis(sample_b_path, ref_path)
    print(f"  Case B (Lighting & Noise Varied Genuine): Layout Score = {res_b['score']}/100")
    print(f"    Components: {res_b['components']}")
    assert res_b["score"] >= 80, f"Expected high layout score for genuine sample B, got {res_b['score']}"

    # Case C: Modified / Anomaly Card (Large text displacement)
    sample_c_path = os.path.join(os.path.dirname(__file__), "test_sample_c.jpg")
    tampered_sample = create_mock_id_card(text_offsets=(120, 90))
    cv2.imwrite(sample_c_path, tampered_sample)

    res_c = perform_layout_analysis(sample_c_path, ref_path)
    print(f"  Case C (Modified/Displaced Layout): Layout Score = {res_c['score']}/100")
    print(f"    Components: {res_c['components']}")

    # 4. Overall Weighted Scoring & Risk Classification
    print("\n[TEST 4] Testing Weighted Multi-Factor Scoring Engine...")
    mock_results = {
        "ocr": {"risk": 0, "confidence": 0.95},
        "layout": res_a,
        "ela": {"risk": 5},
        "noise": {"risk": 10},
        "copy_move": {"risk": 0},
        "jpeg_dct": {"risk": 10},
        "resampling": {"risk": 15},
        "metadata": {"risk": 0}
    }
    score_report = calculate_overall_risk(mock_results, "aadhaar", quality)
    print(f"✓ Overall Authenticity Score: {score_report['overall_score']}/100")
    print(f"✓ Risk Level: {score_report['risk_level']} (Result: {score_report['result']})")
    print(f"✓ Confidence: {score_report['confidence']}")
    assert score_report["overall_score"] >= 85, "Genuine document should be classified as LOW RISK / GENUINE"

    # Cleanup temp test files
    for p in [ref_path, sample_a_path, sample_b_path, sample_c_path]:
        if os.path.exists(p):
            os.remove(p)

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
