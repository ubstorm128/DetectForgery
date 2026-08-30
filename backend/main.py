"""
Document screening API. One endpoint: upload an image, get back an
explainable pass/fail — which check failed, not just a score.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
import shutil
import tempfile
import os

from ocr_mrz import extract_mrz_lines
from mrz_checksum import validate_td3

from forensics.ocr_analysis import perform_ocr_analysis
from forensics.ela import perform_ela
from forensics.noise import perform_noise_analysis
from forensics.copy_move import perform_copy_move_detection
from forensics.compression import perform_compression_analysis
from forensics.metadata import perform_metadata_analysis
from forensics.edges import perform_edge_analysis
from forensics.scoring import calculate_overall_risk

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Veristamp Screening API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ubstorm128.github.io",  # your GitHub Pages origin
        "http://localhost:5500",         # optional: local dev (Live Server etc.)
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def root():
    index_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "index.html"))
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Index page not found"}

@app.get("/scanner.html")
async def scanner():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scanner.html"))
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Not found"}

@app.get("/styles.css")
async def styles():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "styles.css"))
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Not found"}

@app.get("/script.js")
async def script():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "script.js"))
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Not found"}


@app.post("/screen")
async def screen_document(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        lines = extract_mrz_lines(tmp_path)
    finally:
        os.remove(tmp_path)

    # TD3 (passport) is 2 lines of 44 chars — find the pair that fits
    candidates = [l for l in lines if len(l) == 44]
    if len(candidates) < 1:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Could not read a valid MRZ line from this image.",
                "raw_ocr_lines": lines,
            },
        )

    line2 = candidates[-1]  # line 2 carries the checksums
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
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    if not os.path.exists(templates_dir):
        return []
    
    templates = []
    for f in os.listdir(templates_dir):
        if f.endswith(".json"):
            templates.append(f.replace(".json", ""))
    return templates


@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...), document_type: str = Form("passport")):
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Run forensic modules
        res_ocr = perform_ocr_analysis(tmp_path)
        res_ela = perform_ela(tmp_path)
        res_noise = perform_noise_analysis(tmp_path)
        res_copy = perform_copy_move_detection(tmp_path)
        res_comp = perform_compression_analysis(tmp_path)
        res_edge = perform_edge_analysis(tmp_path)
        res_meta = perform_metadata_analysis(tmp_path)

        results = {
            "ocr": res_ocr,
            "ela": res_ela,
            "noise": res_noise,
            "copy_move": res_copy,
            "jpeg_dct": res_comp,
            "resampling": res_edge,
            "metadata": res_meta
        }
        
        report = calculate_overall_risk(results, document_type=document_type)
        
        # Inject Side Detection
        report["detected_side"] = res_ocr.get("detected_side", "unknown")
        
        # Privacy: Mask Aadhaar Numbers
        if document_type == "aadhaar" and "text" in res_ocr:
            import re
            # Mask 12 digit numbers (with optional spaces)
            res_ocr["text"] = re.sub(r'\b\d{4}\s?\d{4}\s?\d{4}\b', 'XXXX XXXX XXXX', res_ocr["text"])
            
        # Attach OCR data so frontend can draw bounding boxes
        report["ocr"] = res_ocr
        
        return report

    finally:
        os.remove(tmp_path)

from pydantic import BaseModel
class CompareSidesRequest(BaseModel):
    front_text: str
    back_text: str
    front_score: int
    back_score: int

@app.post("/api/compare-sides")
async def compare_sides(req: CompareSidesRequest):
    """
    Performs a cross-side data consistency check for dual-sided documents like Aadhaar.
    """
    import re
    # Extract 12 digit aadhaar numbers
    aadhaar_pattern = r'\b\d{4}\s?\d{4}\s?\d{4}\b'
    
    front_nums = set(re.findall(aadhaar_pattern, req.front_text))
    back_nums = set(re.findall(aadhaar_pattern, req.back_text))
    
    # Calculate a combined authenticity score
    combined_score = (req.front_score + req.back_score) // 2
    
    cross_check_status = "PASS"
    anomalies = []
    
    # If both sides found a number, they MUST match
    if front_nums and back_nums:
        intersection = front_nums.intersection(back_nums)
        if not intersection:
            cross_check_status = "FAIL"
            combined_score -= 25 # Heavy penalty for mismatching numbers
            anomalies.append("Aadhaar Number mismatch between Front and Back scans.")
            
    # Classify overall result
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