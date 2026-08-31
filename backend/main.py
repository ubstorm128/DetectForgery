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
from forensics.qr_analysis import perform_qr_analysis
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

    # 2. QR Analysis
    res_qr = perform_qr_analysis(tmp_path)

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
        "qr": res_qr,
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
        aadhaar_pattern = r"\b\d{4}\s?\d{4}\s?\d{4}\b"
        matches = re.findall(aadhaar_pattern, res_ocr["text"])
        if matches:
            res_ocr["aadhaar_number"] = matches[0]

        res_ocr["text"] = re.sub(
            aadhaar_pattern,
            "XXXX XXXX XXXX",
            res_ocr["text"]
        )

    report["detected_side"] = detected_side
    report["qr"] = res_qr
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
        layout_components = report.get("layout", {}).get("components", {})
        ocr_conf = report.get("ocr", {}).get("confidence", 0.0)

        return {
            "overall_score": report.get("overall_score", 90),
            "authenticity_score": report.get("authenticity_score", 90),
            "risk_score": report.get("risk_score", 10),
            "risk_level": report.get("risk_level", "LOW RISK"),
            "confidence": report.get("confidence", 0.90),
            "layout": {
                "score": report.get("layout", {}).get("score", 90),
                "position": layout_components.get("position", 95),
                "size": layout_components.get("size", 92),
                "alignment": layout_components.get("alignment", 95),
                "spacing": layout_components.get("spacing", 92),
                "region_structure": layout_components.get("region_structure", 90),
                "explainable_reasons": report.get("layout", {}).get("explainable_reasons", [])
            },
            "ocr": {
                "score": report.get("checks", {}).get("ocr", {}).get("score", 95),
                "average_confidence": round(ocr_conf, 2),
                "detected_side": report.get("detected_side", "front"),
                "boxes": report.get("ocr", {}).get("boxes", [])
            },
            "image_quality": {
                "score": report.get("image_quality", {}).get("score", 88),
                "sharpness": report.get("image_quality", {}).get("sharpness", 85),
                "brightness": report.get("image_quality", {}).get("brightness", 90),
                "contrast": report.get("image_quality", {}).get("contrast", 88)
            },
            "warnings": report.get("warnings", []),
            "disclaimer": report.get("disclaimer")
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


class CompareSidesRequest(BaseModel):
    front_text: str
    back_text: str
    front_score: int
    back_score: int
    front_aadhaar: str = ""
    back_aadhaar: str = ""


@app.post("/api/compare-sides")
async def compare_sides(req: CompareSidesRequest):
    aadhaar_pattern = r"\b\d{4}\s?\d{4}\s?\d{4}\b"

    front_nums = {req.front_aadhaar} if req.front_aadhaar else set(re.findall(aadhaar_pattern, req.front_text))
    back_nums = {req.back_aadhaar} if req.back_aadhaar else set(re.findall(aadhaar_pattern, req.back_text))
    
    front_nums = {n for n in front_nums if n}
    back_nums = {n for n in back_nums if n}
    
    front_normalized = {re.sub(r"\s+", "", num) for num in front_nums}
    back_normalized = {re.sub(r"\s+", "", num) for num in back_nums}

    combined_score = (req.front_score + req.back_score) // 2
    cross_check_status = "PASS"
    anomalies = []
    matched_number = None

    if front_normalized and back_normalized:
        intersection = front_normalized.intersection(back_normalized)
        if not intersection:
            cross_check_status = "FAIL"
            combined_score = max(0, combined_score - 25)
            anomalies.append("Aadhaar Number mismatch between Front and Back scans.")
        else:
            matched_number = list(intersection)[0]
    elif front_normalized:
        matched_number = list(front_normalized)[0]
    elif back_normalized:
        matched_number = list(back_normalized)[0]

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
        "status": cross_check_status,
        "combined_authenticity_score": combined_score,
        "risk_level": risk_level,
        "classification": classification,
        "anomalies": anomalies,
        "matched_aadhaar": matched_number,
        "front_number": list(front_normalized)[0] if front_normalized else None,
        "back_number": list(back_normalized)[0] if back_normalized else None
    }