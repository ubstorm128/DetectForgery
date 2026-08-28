"""
Document screening API. One endpoint: upload an image, get back an
explainable pass/fail — which check failed, not just a score.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
import shutil
import tempfile
import os

from ocr_mrz import extract_mrz_lines
from mrz_checksum import validate_td3

app = FastAPI(title="Veristamp Screening API")


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