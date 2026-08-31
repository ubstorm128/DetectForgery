"""
Real Reference Cards Test
Tests the full verification pipeline on the actual reference images stored in backend/reference/
"""

import os
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import cv2
sys.path.insert(0, os.path.dirname(__file__))

from main import _process_image_pipeline


def test_real_cards():
    ref_dir = os.path.join(os.path.dirname(__file__), "reference")
    front_path = os.path.join(ref_dir, "front_aadhaar.jpeg")
    back_path = os.path.join(ref_dir, "back_aadhaar.jpeg")

    print("=" * 60)
    print("TESTING REAL AADHAAR REFERENCE CARDS")
    print("=" * 60)

    # 1. Front Card Test
    if os.path.exists(front_path):
        print(f"\n[FRONT CARD TEST]: {front_path}")
        res_front = _process_image_pipeline(front_path, "aadhaar")
        print(f"  Overall Authenticity Score: {res_front.get('overall_score')}/100")
        print(f"  Risk Level: {res_front.get('risk_level')}")
        print(f"  Confidence: {res_front.get('confidence')}")
        print(f"  Detected Side: {res_front.get('detected_side')}")
        print(f"  Layout Score: {res_front.get('layout', {}).get('score')}/100")
        print(f"  Layout Components: {res_front.get('layout', {}).get('components')}")
        print(f"  Explainable Reasons:")
        for r in res_front.get('layout', {}).get('explainable_reasons', []):
            print(f"    {r}")
        print(f"  Image Quality: {res_front.get('image_quality', {}).get('score')}/100")

    # 2. Back Card Test
    if os.path.exists(back_path):
        print(f"\n[BACK CARD TEST]: {back_path}")
        res_back = _process_image_pipeline(back_path, "aadhaar")
        print(f"  Overall Authenticity Score: {res_back.get('overall_score')}/100")
        print(f"  Risk Level: {res_back.get('risk_level')}")
        print(f"  Confidence: {res_back.get('confidence')}")
        print(f"  Detected Side: {res_back.get('detected_side')}")
        print(f"  Layout Score: {res_back.get('layout', {}).get('score')}/100")
        print(f"  Layout Components: {res_back.get('layout', {}).get('components')}")
        print(f"  Image Quality: {res_back.get('image_quality', {}).get('score')}/100")

    print("\n" + "=" * 60)
    print("REAL REFERENCE CARD TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_real_cards()
