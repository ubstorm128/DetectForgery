"""
FastAPI Endpoints Verification Test
Tests all endpoints with mock files and validates schema integrity.
"""

import os
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app


def test_endpoints():
    client = TestClient(app)

    print("=" * 60)
    print("TESTING FASTAPI BACKEND API ENDPOINTS")
    print("=" * 60)

    # 1. Health check
    print("\n[API 1] Testing GET /health...")
    r = client.get("/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print(f"✓ GET /health -> {r.json()}")

    # 2. Templates
    print("\n[API 2] Testing GET /api/templates...")
    r = client.get("/api/templates")
    assert r.status_code == 200
    print(f"✓ GET /api/templates -> {r.json()}")

    # 3. Static routes
    print("\n[API 3] Testing Static Page Endpoints (/scanner.html, /styles.css, /script.js)...")
    assert client.get("/scanner.html").status_code == 200
    assert client.get("/styles.css").status_code == 200
    assert client.get("/script.js").status_code == 200
    print("✓ Static asset routes verified successfully")

    # 4. POST /api/analyze-image
    print("\n[API 4] Testing POST /api/analyze-image with image file...")
    ref_path = os.path.join(os.path.dirname(__file__), "reference", "front_aadhaar.jpeg")
    with open(ref_path, "rb") as f:
        r = client.post(
            "/api/analyze-image",
            files={"file": ("front_aadhaar.jpeg", f, "image/jpeg")},
            data={"document_type": "aadhaar"}
        )
    assert r.status_code == 200, f"Analyze image failed: {r.text}"
    data = r.json()
    print(f"✓ Overall Score: {data.get('overall_score')}, Risk Level: {data.get('risk_level')}")
    print(f"✓ Layout Score: {data.get('layout', {}).get('score')}")
    print(f"✓ Image Quality: {data.get('image_quality', {}).get('score')}")
    assert "layout" in data and "image_quality" in data and "confidence" in data

    # 5. POST /analyze-id (Standard Schema Endpoint)
    print("\n[API 5] Testing POST /analyze-id (Standard REST Endpoint)...")
    with open(ref_path, "rb") as f:
        r = client.post(
            "/analyze-id",
            files={"file": ("front_aadhaar.jpeg", f, "image/jpeg")},
            data={"document_type": "aadhaar"}
        )
    assert r.status_code == 200, f"Analyze-id failed: {r.text}"
    std_data = r.json()
    print(f"✓ Standard Response:")
    print(f"  Overall Score: {std_data['overall_score']}")
    print(f"  Risk Level: {std_data['risk_level']}")
    print(f"  Layout Details: {std_data['layout']}")
    print(f"  OCR Score: {std_data['ocr']['score']}")
    print(f"  Image Quality: {std_data['image_quality']}")
    assert "position" in std_data["layout"]
    assert "size" in std_data["layout"]
    assert "alignment" in std_data["layout"]
    assert "spacing" in std_data["layout"]
    assert "region_structure" in std_data["layout"]

    # 6. POST /api/compare-sides
    print("\n[API 6] Testing POST /api/compare-sides...")
    compare_payload = {
        "front_text": "Government of India 1234 5678 9012 DOB 15/08/1990",
        "back_text": "Address 1234 5678 9012 PIN 110001",
        "front_score": 92,
        "back_score": 90
    }
    r = client.post("/api/compare-sides", json=compare_payload)
    assert r.status_code == 200, f"Compare sides failed: {r.text}"
    cmp_res = r.json()
    print(f"✓ Compare Sides -> {cmp_res}")
    assert cmp_res["status"] == "PASS"

    print("\n" + "=" * 60)
    print("ALL API ENDPOINTS TESTED AND VERIFIED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_endpoints()
