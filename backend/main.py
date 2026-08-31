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
from forensics.layout_analysis import perform_layout_analysis
from forensics.metadata import perform_metadata_analysis
from forensics.ela import perform_ela
from forensics.noise import perform_noise_analysis
from forensics.copy_move import perform_copy_move_detection
from forensics.compression import perform_compression_analysis
from forensics.edges import perform_edge_analysis
from forensics.scoring import calculate_overall_risk
from services.perspective import correct_perspective_and_normalize
from services.ocr_service import extract_ocr_data
import json


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

    # 1. Early Perspective Crop & Normalization
    try:
        with open(f"templates/{document_type}.json", "r") as f:
            template_config = json.load(f)
            template_config = template_config.get("front_side", template_config) # Default to front side rules for sizing
    except:
        template_config = {}
        
    t_width = template_config.get("card_normalization", {}).get("normalized_size", {}).get("width", 1500)
    t_height = template_config.get("card_normalization", {}).get("normalized_size", {}).get("height", 950)
    
    rectified_img, persp_meta = correct_perspective_and_normalize(raw_img, target_width=t_width, target_height=t_height)
    
    # Save cropped image temporarily for OCR and Layout
    cropped_tmp_path = tmp_path + "_cropped.jpg"
    cv2.imwrite(cropped_tmp_path, rectified_img)

    # 2. OCR Analysis on Cropped Image
    res_ocr = extract_ocr_data(cropped_tmp_path)
    # Map status to avoid breaking other modules
    if res_ocr.get("status") == "failed":
        res_ocr["risk"] = 0
        res_ocr["confidence"] = 0.0
        res_ocr["anomalies"] = [res_ocr.get("error", "OCR failure")]
    else:
        avg_conf = res_ocr.get("confidence", 0.0)
        risk_score = 0
        if avg_conf < 0.30 and len(res_ocr.get("boxes", [])) > 0:
            risk_score = 15
        elif len(res_ocr.get("boxes", [])) == 0:
            risk_score = 25
        res_ocr["risk"] = risk_score
        res_ocr["anomalies"] = []
    detected_side = res_ocr.get("detected_side", "unknown")

    # 3. Multi-factor Early Exit Validation (Strict Pre-Validation)
    from card_detectors.common.validator import detect_supported_card
    
    validation_result = detect_supported_card(cropped_tmp_path, document_type, res_ocr, threshold=0.45)
    
    print("\n--- Card Detection Debug Log ---")
    for log_entry in validation_result.get("debug_log", []):
        print(log_entry)
    print("--------------------------------\n")
    
    if not validation_result.get("detected", False):
        if os.path.exists(cropped_tmp_path): os.remove(cropped_tmp_path)
        return {
            "document_type": "unknown",
            "is_aadhaar": False,
            "side": None,
            "document_confidence": validation_result.get("confidence", 0.0),
            "score": None,
            "status": "REJECTED",
            "reason": f"Uploaded image is not an {document_type.capitalize()} card",
            "debug_log": validation_result.get("debug_log", [])
        }

    # 4. Reference-based Structural Layout Analysis (on Cropped Image)
    reference_dir = os.path.join(os.path.dirname(__file__), "reference")
    if detected_side == "front":
        reference_path = os.path.join(reference_dir, "front_aadhaar.jpeg")
    elif detected_side == "back":
        reference_path = os.path.join(reference_dir, "back_aadhaar.jpeg")
    else:
        reference_path = os.path.join(reference_dir, "front_aadhaar.jpeg")

    res_layout = perform_layout_analysis(
        image_path=cropped_tmp_path,
        reference_path=reference_path if os.path.exists(reference_path) else None,
        document_type=document_type,
        precomputed_ocr=res_ocr,
        persp_meta=persp_meta
    )
    
    if os.path.exists(cropped_tmp_path):
        os.remove(cropped_tmp_path)

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
    report["side"] = detected_side
    report["layout"] = res_layout
    report["ocr"] = res_ocr
    report["document_type"] = document_type
    report["is_aadhaar"] = (document_type.lower() == "aadhaar")
    report["document_confidence"] = validation_result.get("confidence", 1.0)
    
    if report.get("classification") == "LIKELY_FAKE":
        report["status"] = "INVALID"
    elif report.get("classification") == "SUSPICIOUS":
        report["status"] = "SUSPICIOUS"
    else:
        report["status"] = "VALID"

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

