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

# Validators
from app.forensics.layout_analysis import perform_layout_analysis
import json

router = APIRouter()

# Initialize AI Models
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
        # 1. Image Quality Assessment (Pre-verification gate)
        # -------------------------------------------------------------------
        quality_report = assess_image_quality(raw_img)
        quality_score = quality_report.get("score", 0)
        
        if quality_score < 40:
            return JSONResponse({
                "success": True,
                "document": {
                    "type": "unknown",
                    "confidence": 0.0,
                    "side": "unknown"
                },
                "verification": {
                    "status": "insufficient_quality",
                    "is_valid_document": False,
                    "authenticity_score": None
                },
                "errors": [{"code": "POOR_QUALITY", "message": "The image is too blurry or unclear to verify."}]
            })

        # -------------------------------------------------------------------
        # 2. AI Document Detection
        # -------------------------------------------------------------------
        setattr(raw_img, 'filename', file.filename)
        detection_result = doc_detector.detect(raw_img)
        if not detection_result.get("document_detected"):
            return JSONResponse({
                "success": True,
                "document": {
                    "type": "non_document",
                    "confidence": detection_result.get("confidence", 0.0),
                    "side": "unknown"
                },
                "verification": {
                    "status": "rejected",
                    "is_valid_document": False,
                    "authenticity_score": None
                },
                "errors": [{"code": "NO_DOCUMENT", "message": "This image does not appear to contain an ID document."}]
            })

        # -------------------------------------------------------------------
        # 3. Automatic Card Cropping
        # -------------------------------------------------------------------
        bbox = detection_result.get("bounding_box")
        cropped_img = crop_to_bounding_box(raw_img, bbox)

        # -------------------------------------------------------------------
        # 4. AI Document Classification (Is it Aadhaar, PAN, DL?)
        # -------------------------------------------------------------------
        classification_result = doc_classifier.classify(cropped_img, filename=file.filename)
        doc_type = classification_result.get("document_type", "unknown")
        
        # Anti-False-Positive Rule: Hard Document Identity Gate
        if doc_type != "aadhaar":
            return JSONResponse({
                "success": True,
                "document": {
                    "type": doc_type,
                    "confidence": classification_result.get("confidence", 0.0),
                    "side": "unknown"
                },
                "verification": {
                    "status": "rejected",
                    "is_valid_document": False,
                    "authenticity_score": None
                },
                "errors": [{"code": "NOT_AADHAAR", "message": f"This document is not an Aadhaar card (detected: {doc_type})."}]
            })

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
        ocr_res = extract_ocr_data(rectified_tmp_path)
        ocr_confidence = ocr_res.get("confidence")
        ocr_status = ocr_res.get("status", "failed")
        detected_side = ocr_res.get("detected_side", "unknown")
        
        if ocr_status == "failed":
            return JSONResponse({
                "success": True,
                "document": {
                    "type": "aadhaar",
                    "confidence": classification_result.get("confidence", 0.95),
                    "side": detected_side
                },
                "verification": {
                    "status": "ocr_failure",
                    "is_valid_document": False,
                    "authenticity_score": None
                },
                "ocr": {
                    "status": "failed",
                    "confidence": None
                },
                "errors": [{"code": "OCR_FAILED", "message": "The document was detected, but text could not be read reliably."}]
            })

        # -------------------------------------------------------------------
        # 7. Document-Specific JSON Validation (Layout & Visuals)
        # -------------------------------------------------------------------
        layout_res = perform_layout_analysis(
            image_path=rectified_tmp_path,
            reference_path=None,
            document_type="aadhaar",
            precomputed_ocr=ocr_res,
            persp_meta=persp_meta
        )

        # -------------------------------------------------------------------
        # 8. Forgery / Manipulation Analysis
        # -------------------------------------------------------------------
        res_ela = perform_ela(tmp_path)
        res_noise = perform_noise_analysis(tmp_path)
        res_copy = perform_copy_move_detection(tmp_path)
        
        ela_risk = res_ela.get("risk", 0)
        noise_risk = res_noise.get("risk", 0)
        copy_risk = res_copy.get("risk", 0)
        
        manipulation_risk = (ela_risk * 0.4) + (noise_risk * 0.3) + (copy_risk * 0.3)
        manipulation_score = 1.0 - (manipulation_risk / 100.0)

        # -------------------------------------------------------------------
        # 9. Final Verification Result (Hierarchical Aggregation)
        # -------------------------------------------------------------------
        layout_score = layout_res.get("score", 0) / 100.0
        
        # Calculate final authenticity score only if all gates passed
        final_score = (layout_score * 0.5) + (ocr_confidence * 0.2) + (manipulation_score * 0.3)
        
        if layout_res.get("major_layout_mismatch", False):
            final_score = min(final_score, 0.20)
            
        status = "verified"
        if final_score < 0.65:
            status = "fake"
        elif final_score < 0.80:
            status = "suspicious"

        if os.path.exists(rectified_tmp_path):
            os.remove(rectified_tmp_path)

        # Build stable response schema
        response_data = {
            "success": True,
            "document": {
                "type": "aadhaar",
                "confidence": classification_result.get("confidence", 0.95),
                "side": detected_side
            },
            "verification": {
                "status": status,
                "is_valid_document": status == "verified" or status == "suspicious",
                "authenticity_score": int(final_score * 100)
            },
            "ocr": {
                "status": "success" if ocr_status == "completed" else "partial",
                "confidence": round(ocr_confidence, 2) if ocr_confidence is not None else None
            },
            "forensics": {
                "layout": int(layout_score * 100),
                "manipulation": int(manipulation_score * 100),
                "warnings": layout_res.get("warnings", [])
            },
            "errors": []
        }

        # For frontend backward compatibility, include the old 'result' block momentarily
        # We will phase this out as the frontend script.js is updated.
        response_data["result"] = {
            "status": "likely_valid" if status == "verified" else "likely_fake" if status == "fake" else "suspicious",
            "score": int(final_score * 100)
        }
        
        # Adding analysis_breakdown for frontend compatibility
        response_data["validation"] = {
            "layout": layout_score,
            "text": ocr_confidence,
            "security_features": layout_score
        }
        response_data["manipulation_analysis"] = {
            "score": manipulation_score,
            "status": "low_suspicion" if manipulation_score > 0.7 else "high_suspicion"
        }
        response_data["image_quality"] = {
            "score": quality_score / 100.0,
            "status": "good" if quality_score > 70 else "poor"
        }

        return JSONResponse(response_data)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
