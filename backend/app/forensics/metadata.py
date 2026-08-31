"""
Metadata Extraction
Extracts EXIF data and checks for signs of image editing software.
"""
from PIL import Image
from PIL.ExifTags import TAGS
import os

def perform_metadata_analysis(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {"risk": 0, "software": "unknown", "error": "File not found"}
        
    try:
        img = Image.open(image_path)
        exif_data = img.getexif()
    except Exception as e:
        return {"risk": 0, "software": "unknown", "error": str(e)}
        
    if not exif_data:
        return {"risk": 0, "software": "none"}
        
    software = "unknown"
    risk_score = 0
    warnings = []
    
    # Iterate through EXIF tags
    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, tag_id)
        if tag == "Software":
            software = str(value).lower()
            if "photoshop" in software or "gimp" in software or "paint" in software:
                risk_score = 80
                warnings.append(f"Edited with software: {value}")
            else:
                warnings.append(f"Processed by: {value}")
                
    return {
        "risk": risk_score,
        "software": software,
        "warnings": warnings
    }
