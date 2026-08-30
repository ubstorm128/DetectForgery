"""
Document screening API.
Runs OCR, QR, layout and forensic analysis.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import shutil
import tempfile
import os
import re

from ocr_mrz import extract_mrz_lines
from mrz_checksum import validate_td3

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


app = FastAPI(title="Veristamp Screening API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ubstorm128.github.io",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    index_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "index.html")
    )

    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {"error": "Index page not found"}


@app.get("/scanner.html")
async def scanner():
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scanner.html")
    )

    if os.path.exists(path):
        return FileResponse(path)

    return {"error": "Not found"}


@app.get("/styles.css")
async def styles():
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "styles.css")
    )

    if os.path.exists(path):
        return FileResponse(path)

    return {"error": "Not found"}


@app.get("/script.js")
async def script():
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "script.js")
    )

    if os.path.exists(path):
        return FileResponse(path)

    return {"error": "Not found"}


@app.post("/screen")
async def screen_document(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"

    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False
    ) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        lines = extract_mrz_lines(tmp_path)

    finally:
        os.remove(tmp_path)

    candidates = [l for l in lines if len(l) == 44]

    if len(candidates) < 1:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Could not read a valid MRZ line from this image.",
                "raw_ocr_lines": lines,
            },
        )

    line2 = candidates[-1]
    result = validate_td3(line2)

    return {
        "filename": file.filename,
        "raw_ocr_lines": lines,
        "screening_result": result,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/templates")
async def get_templates():
    templates_dir = os.path.join(
        os.path.dirname(__file__),
        "templates"
    )

    if not os.path.exists(templates_dir):
        return []

    return [
        f.replace(".json", "")
        for f in os.listdir(templates_dir)
        if f.endswith(".json")
    ]


@app.post("/api/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    document_type: str = Form("aadhaar")
):
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"

    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False
    ) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # -------------------------------------------------
        # OCR
        # -------------------------------------------------

        res_ocr = perform_ocr_analysis(tmp_path)

        # -------------------------------------------------
        # QR
        # -------------------------------------------------

        res_qr = perform_qr_analysis(tmp_path)

        # -------------------------------------------------
        # Reference-based Layout Analysis
        # -------------------------------------------------

        detected_side = res_ocr.get("detected_side", "unknown")

        reference_dir = os.path.join(
            os.path.dirname(__file__),
            "reference"
        )

        if detected_side == "front":
            reference_path = os.path.join(
                reference_dir,
                "front_aadhaar.jpeg"
            )

        elif detected_side == "back":
            reference_path = os.path.join(
                reference_dir,
                "back_aadhaar.jpeg"
            )

        else:
            reference_path = None

        if reference_path and os.path.exists(reference_path):

            res_layout = perform_layout_analysis(
                tmp_path,
                reference_path
            )

        else:

            res_layout = {
                "status": "skipped",
                "score": 0,
                "risk": 0,
                "error": "Could not determine Aadhaar side"
            }

        # -------------------------------------------------
        # Other forensic modules
        # -------------------------------------------------

        res_ela = perform_ela(tmp_path)
        res_noise = perform_noise_analysis(tmp_path)
        res_copy = perform_copy_move_detection(tmp_path)
        res_comp = perform_compression_analysis(tmp_path)
        res_edge = perform_edge_analysis(tmp_path)
        res_meta = perform_metadata_analysis(tmp_path)

        # -------------------------------------------------
        # Combine Results
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Calculate Score
        # -------------------------------------------------

        report = calculate_overall_risk(
            results,
            document_type=document_type
        )

        # -------------------------------------------------
        # Additional Results
        # -------------------------------------------------

        report["detected_side"] = detected_side
        report["qr"] = res_qr
        report["layout"] = res_layout

        # -------------------------------------------------
        # Privacy: Mask Aadhaar Number
        # -------------------------------------------------

        if (
            document_type == "aadhaar"
            and "text" in res_ocr
        ):
            res_ocr["text"] = re.sub(
                r"\b\d{4}\s?\d{4}\s?\d{4}\b",
                "XXXX XXXX XXXX",
                res_ocr["text"]
            )

        # -------------------------------------------------
        # OCR Bounding Boxes
        # -------------------------------------------------

        report["ocr"] = res_ocr

        return report

    finally:
        os.remove(tmp_path)


class CompareSidesRequest(BaseModel):
    front_text: str
    back_text: str
    front_score: int
    back_score: int


@app.post("/api/compare-sides")
async def compare_sides(req: CompareSidesRequest):

    aadhaar_pattern = r"\b\d{4}\s?\d{4}\s?\d{4}\b"

    front_nums = set(
        re.findall(aadhaar_pattern, req.front_text)
    )

    back_nums = set(
        re.findall(aadhaar_pattern, req.back_text)
    )

    combined_score = (
        req.front_score + req.back_score
    ) // 2

    cross_check_status = "PASS"
    anomalies = []

    if front_nums and back_nums:

        front_normalized = {
            re.sub(r"\s+", "", num)
            for num in front_nums
        }

        back_normalized = {
            re.sub(r"\s+", "", num)
            for num in back_nums
        }

        if not front_normalized.intersection(
            back_normalized
        ):
            cross_check_status = "FAIL"

            combined_score = max(
                0,
                combined_score - 25
            )

            anomalies.append(
                "Aadhaar Number mismatch between "
                "Front and Back scans."
            )

    if combined_score >= 85:
        classification = "GENUINE"

    elif combined_score >= 60:
        classification = "SUSPICIOUS"

    else:
        classification = "LIKELY_FAKE"

    return {
        "status": cross_check_status,
        "combined_authenticity_score": combined_score,
        "classification": classification,
        "anomalies": anomalies
    }