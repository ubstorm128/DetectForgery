from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import shutil
import os
import cv2

# Import modular components
from app.models.document_detector import YOLODocumentDetector
from app.models.document_classifier import YOLODocumentClassifier
from app.preprocessing.quality import assess_image_quality
from app.preprocessing.crop import crop_to_bounding_box
from app.preprocessing.perspective import correct_perspective_and_normalize
from app.ocr.paddleocr_engine import extract_ocr_data

# Forgery analysis
from app.forensics.ela import perform_ela
from app.forensics.noise import perform_noise_analysis
from app.forensics.copy_move import perform_copy_move_detection

# Validators (We'll use layout_analysis directly for now as Aadhaar validator logic)
from app.forensics.layout_analysis import perform_layout_analysis
import json

router = APIRouter()

# Initialize AI Models (Using mock for now until weights are provided)
# In production, pass the path to the trained .pt files
doc_detector = YOLODocumentDetector(model_path=None)
doc_classifier = YOLODocumentClassifier(model_path=None)

@router.post("/api/verify")
async def verify_document(file: UploadFile = File(...), expected_type: str = Form("auto")):
    """
    Strict Verification Pipeline with Anti-False-Positive guarantees.
    """
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        raw_img = cv2.imread(tmp_path)
        if raw_img is None:
            raise HTTPException(status_code=400, detail="Invalid image file")

        # -------------------------------------------------------------------
        # 1. AI Document Detection
        # -------------------------------------------------------------------
        detection_result = doc_detector.detect(raw_img)
        if not detection_result.get("document_detected"):
            return JSONResponse({
                "success": True,
                "document": {
                    "detected": False,
                    "type": "unknown",
                    "confidence": detection_result.get("confidence", 0.0)
                },
                "result": {
                    "status": "no_supported_document",
                    "message": "No supported identity document detected. Please upload a clear image of the document."
                }
            })

        # -------------------------------------------------------------------
        # 2. Automatic Card Cropping
        # -------------------------------------------------------------------
        bbox = detection_result.get("bounding_box")
        cropped_img = crop_to_bounding_box(raw_img, bbox)

        # -------------------------------------------------------------------
        # 3. AI Document Classification (Is it Aadhaar, PAN, DL?)
        # -------------------------------------------------------------------
        classification_result = doc_classifier.classify(cropped_img)
        doc_type = classification_result.get("document_type", "unknown")
        
        # Anti-False-Positive Rule: If the user uploaded a PAN card, do NOT run Aadhaar validation.
        if doc_type != "aadhaar":
            return JSONResponse({
                "success": True,
                "document": {
                    "detected": True,
                    "type": doc_type,
                    "confidence": classification_result.get("confidence", 0.0)
                },
                "aadhaar_verification": {
                    "status": "not_applicable",
                    "message": f"Document detected as {doc_type}. Aadhaar verification is not applicable."
                }
            })

        # -------------------------------------------------------------------
        # 4. Image Quality Assessment
        # -------------------------------------------------------------------
        quality_report = assess_image_quality(cropped_img)
        # If quality is abysmally poor, we could reject here. 
        # For now, we continue and report the quality score.

        # -------------------------------------------------------------------
        # 5. Perspective Correction (Normalization)
        # -------------------------------------------------------------------
        rectified_img, persp_meta = correct_perspective_and_normalize(
            cropped_img, target_width=1500, target_height=950
        )
        
        rectified_tmp_path = tmp_path + "_rectified.jpg"
        cv2.imwrite(rectified_tmp_path, rectified_img)

        # -------------------------------------------------------------------
        # 6. OCR Extraction
        # -------------------------------------------------------------------
        # Note: ocr_service reads from path, so we pass the saved rectified image
        ocr_res = extract_ocr_data(rectified_tmp_path)
        ocr_confidence = ocr_res.get("confidence", 0.0)

        # -------------------------------------------------------------------
        # 7. Document-Specific JSON Validation (Layout & Visuals)
        # -------------------------------------------------------------------
        # Using existing perform_layout_analysis as the Aadhaar Validator
        layout_res = perform_layout_analysis(
            image_path=rectified_tmp_path,
            reference_path=None, # Reference path logic can be injected here
            document_type="aadhaar",
            precomputed_ocr=ocr_res,
            persp_meta=persp_meta
        )

        # -------------------------------------------------------------------
        # 8. Forgery / Manipulation Analysis (on the raw image)
        # -------------------------------------------------------------------
        res_ela = perform_ela(tmp_path)
        res_noise = perform_noise_analysis(tmp_path)
        res_copy = perform_copy_move_detection(tmp_path)
        
        # Calculate manipulation score (100 = heavily manipulated, 0 = pristine)
        # We invert it for the final schema so 1.0 = genuine, 0.0 = fake
        ela_risk = res_ela.get("risk", 0)
        noise_risk = res_noise.get("risk", 0)
        copy_risk = res_copy.get("risk", 0)
        
        manipulation_risk = (ela_risk * 0.4) + (noise_risk * 0.3) + (copy_risk * 0.3)
        manipulation_score = 1.0 - (manipulation_risk / 100.0)

        # -------------------------------------------------------------------
        # 9. Final Verification Result
        # -------------------------------------------------------------------
        layout_score = layout_res.get("score", 0) / 100.0
        quality_score = quality_report.get("score", 0) / 100.0
        
        # Compute final authenticity
        final_score = (layout_score * 0.4) + (ocr_confidence * 0.3) + (manipulation_score * 0.3)
        
        # Force low score if major layout mismatch (Strict rule)
        if layout_res.get("major_layout_mismatch", False):
            final_score = min(final_score, 0.20)
            
        status = "likely_valid"
        if final_score < 0.65:
            status = "likely_fake"
        elif final_score < 0.80:
            status = "suspicious"

        # Cleanup
        if os.path.exists(rectified_tmp_path):
            os.remove(rectified_tmp_path)

        return JSONResponse({
            "success": True,
            "document": {
                "detected": True,
                "type": "aadhaar",
                "confidence": classification_result.get("confidence", 0.95)
            },
            "image_quality": {
                "score": round(quality_score, 2),
                "status": "good" if quality_score > 0.7 else "poor"
            },
            "ocr": {
                "status": "completed",
                "confidence": round(ocr_confidence, 2)
            },
            "validation": {
                "layout": round(layout_score, 2),
                "text": round(ocr_confidence, 2), # Simplified for schema mapping
                "security_features": round(layout_score, 2)
            },
            "manipulation_analysis": {
                "score": round(1.0 - manipulation_score, 2), # 0 = no manipulation
                "status": "low_suspicion" if manipulation_score > 0.7 else "high_suspicion"
            },
            "result": {
                "status": status,
                "score": round(final_score, 2)
            }
        })

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
