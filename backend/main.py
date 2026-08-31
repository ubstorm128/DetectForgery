"""
Document Screening & ID Verification API.
Runs OCR, QR, Perspective Correction, Layout, and Forensic Analysis.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import shutil
import tempfile
import os
import re
import cv2

from services.image_quality import assess_image_quality
from forensics.ocr_analysis import perform_ocr_analysis
from forensics.layout_analysis import perform_layout_analysis
from forensics.ela import perform_ela
from forensics.noise import perform_noise_analysis
from forensics.copy_move import perform_copy_move_detection
from forensics.compression import perform_compression_analysis
from forensics.metadata import perform_metadata_analysis
from forensics.edges import perform_edge_analysis
from forensics.scoring import calculate_overall_risk


app = FastAPI(
    title="Veristamp ID Verification & Document Screening API",
    description="Automated structural layout, OCR, and multi-factor image forensic verification.",
    version="2.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ubstorm128.github.io",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://detectforgery.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_static_path(filename: str) -> str:
    dev_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", filename))
    if os.path.exists(dev_path):
        return dev_path
    return os.path.abspath(os.path.join(os.path.dirname(__file__), filename))


@app.get("/")
@app.get("/index.html")
async def root():
    path = get_static_path("index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Index page not found"}


@app.get("/scanner.html")
async def scanner():
    path = get_static_path("scanner.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Scanner page not found"}


@app.get("/styles.css")
async def styles():
    path = get_static_path("styles.css")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Styles not found"}


@app.get("/script.js")
async def script():
    path = get_static_path("script.js")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Script not found"}


@app.get("/ficon.png")
async def ficon():
    path = get_static_path("ficon.png")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Favicon not found"}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/templates")
async def get_templates():
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    if not os.path.exists(templates_dir):
        return []
    return [
        f.replace(".json", "")
        for f in os.listdir(templates_dir)
        if f.endswith(".json")
    ]


def _process_image_pipeline(tmp_path: str, document_type: str = "aadhaar") -> dict:
    """Internal shared verification pipeline for an uploaded document image."""
    # 0. Image Quality Check
    raw_img = cv2.imread(tmp_path)
    quality_report = assess_image_quality(raw_img)

    # 1. OCR Analysis (with PaddleOCR)
    res_ocr = perform_ocr_analysis(tmp_path)
    detected_side = res_ocr.get("detected_side", "unknown")

    # --- NEW: Multi-factor Early Exit if Card Not Detected ---
    from card_detectors.validator import detect_supported_card
    
    validation_result = detect_supported_card(tmp_path, document_type, res_ocr, threshold=0.45)
    
    # Print debug log to console
    print("\n--- Card Detection Debug Log ---")
    for log_entry in validation_result.get("debug_log", []):
        print(log_entry)
    print("--------------------------------\n")
    
    if not validation_result.get("detected", False):
        return {
            "error": "CARD_NOT_DETECTED",
            "message": f"No valid {document_type.upper()} card detected in the image.",
            "debug_log": validation_result.get("debug_log", [])
        }
    # --------------------------------------------

    # 3. Reference-based Structural Layout Analysis
    reference_dir = os.path.join(os.path.dirname(__file__), "reference")
    if detected_side == "front":
        reference_path = os.path.join(reference_dir, "front_aadhaar.jpeg")
    elif detected_side == "back":
        reference_path = os.path.join(reference_dir, "back_aadhaar.jpeg")
    else:
        reference_path = os.path.join(reference_dir, "front_aadhaar.jpeg")

    res_layout = perform_layout_analysis(
        image_path=tmp_path,
        reference_path=reference_path if os.path.exists(reference_path) else None,
        document_type=document_type
    )

    # 4. Forensic Modules (analyzing original image)
    res_ela = perform_ela(tmp_path)
    res_noise = perform_noise_analysis(tmp_path)
    res_copy = perform_copy_move_detection(tmp_path)
    res_comp = perform_compression_analysis(tmp_path)
    res_edge = perform_edge_analysis(tmp_path)
    res_meta = perform_metadata_analysis(tmp_path)

    # 5. Combine and Calculate Weighted Authenticity Score
    results = {
        "ocr": res_ocr,
        "layout": res_layout,
        "ela": res_ela,
        "noise": res_noise,
        "copy_move": res_copy,
        "jpeg_dct": res_comp,
        "resampling": res_edge,
        "metadata": res_meta
    }

    report = calculate_overall_risk(
        results,
        document_type=document_type,
        image_quality_data=quality_report
    )

    # 6. Privacy: Mask Aadhaar Number if applicable
    if document_type == "aadhaar" and "text" in res_ocr:
        aadhaar_pattern = r"\b\d{4}[\s\-\.]*\d{4}[\s\-\.]*\d{4}\b"
        matches = re.findall(aadhaar_pattern, res_ocr["text"])
        if matches:
            res_ocr["aadhaar_number"] = matches[0]

        res_ocr["text"] = re.sub(
            aadhaar_pattern,
            "XXXX XXXX XXXX",
            res_ocr["text"]
        )

    report["detected_side"] = detected_side
    report["layout"] = res_layout
    report["ocr"] = res_ocr

    return report


@app.post("/api/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    document_type: str = Form("aadhaar")
):
    """Primary document screening endpoint for UI."""
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        return _process_image_pipeline(tmp_path, document_type=document_type)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/analyze-id")
async def analyze_id(
    file: UploadFile = File(...),
    document_type: str = Form("aadhaar")
):
    """
    Standardized REST API endpoint returning structured verification report.
    """
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        report = _process_image_pipeline(tmp_path, document_type=document_type)
        if report.get("error") == "CARD_NOT_DETECTED":
            return {
                "document": {
                    "type": document_type,
                    "side": "unknown",
                    "detected": False
                },
                "verification": {
                    "status": "invalid",
                    "score": 0
                }
            }

        score = report.get("overall_score", 0)
        classification = report.get("classification", "LIKELY_FAKE")
        
        return {
            "document": {
                "type": document_type,
                "side": report.get("detected_side", "unknown"),
                "detected": True
            },
            "verification": {
                "status": "valid" if classification != "LIKELY_FAKE" else "invalid",
                "score": score
            }
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


from card_detectors.aadhaar import AadhaarDetector
from card_detectors.pan import PANDetector

class CompareSidesRequest(BaseModel):
    document_type: str = "aadhaar"
    front_text: str = ""
    back_text: str = ""
    front_boxes: list = []
    back_boxes: list = []
    front_score: int = 0
    back_score: int = 0
    front_aadhaar: str = ""
    back_aadhaar: str = ""


@app.post("/api/compare-sides")
async def compare_sides(req: CompareSidesRequest):
    if req.document_type.lower() == "pan":
        detector = PANDetector()
    else:
        detector = AadhaarDetector()
        
    front_result = detector.detect_card_number(req.front_boxes, req.front_text)
    back_result = detector.detect_card_number(req.back_boxes, req.back_text)
    
    # --- DEBUG LOGGING ---
    print("\n" + "="*20 + " CARD NUMBER DEBUG " + "="*20)
    print(f"Card Type: {req.document_type.upper()}")
    
    print("\nSide: FRONT")
    print("Raw OCR Text:", req.front_text)
    print("Raw Boxes:", [b.get("text") for b in req.front_boxes])
    print("Selected:", front_result)
    
    print("\nSide: BACK")
    print("Raw OCR Text:", req.back_text)
    print("Raw Boxes:", [b.get("text") for b in req.back_boxes])
    print("Selected:", back_result)
    print("="*60 + "\n")
    # ---------------------
    
    # Fallback to the pre-extracted numbers if the detector fails and the frontend provided them
    if not front_result["detected"] and req.front_aadhaar:
        front_result = {"raw_text": req.front_aadhaar, "normalized": detector.normalize(req.front_aadhaar), "confidence": 0.9, "detected": True}
    if not back_result["detected"] and req.back_aadhaar:
        back_result = {"raw_text": req.back_aadhaar, "normalized": detector.normalize(req.back_aadhaar), "confidence": 0.9, "detected": True}

    front_norm = front_result.get("normalized")
    back_norm = back_result.get("normalized")
    
    status = "NOT_DETECTED"
    if front_result["detected"] and back_result["detected"]:
        if front_norm == back_norm:
            status = "MATCH"
        else:
            status = "MISMATCH"
            
    combined_score = (req.front_score + req.back_score) // 2
    classification = "GENUINE"
    risk_level = "LOW RISK"
    anomalies = []
    
    if status == "MISMATCH":
        classification = "LIKELY_FAKE"
        risk_level = "HIGH RISK"
        combined_score = min(combined_score, 40)
        anomalies.append(f"{req.document_type.upper()} Number mismatch between Front and Back scans.")
    elif status == "NOT_DETECTED":
        # Do not treat OCR failure as evidence of fraud.
        pass
    
    if classification != "LIKELY_FAKE":
        if combined_score >= 80:
            classification = "GENUINE"
            risk_level = "LOW RISK"
        elif combined_score >= 65:
            classification = "SUSPICIOUS"
            risk_level = "MEDIUM RISK"
        else:
            classification = "LIKELY_FAKE"
            risk_level = "HIGH RISK"

    return {
        # Old fields for UI backwards compatibility
        "status": status,
        "combined_authenticity_score": combined_score,
        "risk_level": risk_level,
        "classification": classification,
        "anomalies": anomalies,
        "matched_aadhaar": front_norm if status == "MATCH" else None,
        "front_number": front_norm,
        "back_number": back_norm,
        
        # New Structured Response as per spec
        "card_type": req.document_type.upper(),
        "front": {
            "card_number": front_result
        },
        "back": {
            "card_number": back_result
        },
        "comparison": {
            "status": status
        }
    }