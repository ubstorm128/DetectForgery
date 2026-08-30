"""
JPEG/DCT Compression Analysis
Analyzes JPEG compression characteristics. Regions that have been edited and re-saved 
often exhibit different block artifact structures than the rest of the image.
"""
import cv2
import numpy as np
import os

def perform_compression_analysis(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {"risk": 0, "error": "File not found"}
        
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return {"risk": 0, "error": "Could not read image"}
        
    # Simplified approach: detect 8x8 JPEG block boundaries.
    # JPEG compression creates discontinuities at 8x8 pixel boundaries.
    # We can measure the strength of these discontinuities.
    h, w = image.shape
    
    # We only care about block boundaries
    # Calculate differences across vertical and horizontal 8x8 boundaries
    diff_h = 0
    diff_v = 0
    count_h = 0
    count_v = 0
    
    # Analyze horizontal boundaries (rows 8, 16, 24...)
    for y in range(8, h - 1, 8):
        diff_h += np.sum(np.abs(image[y, :].astype(int) - image[y-1, :].astype(int)))
        count_h += w
        
    # Analyze vertical boundaries (cols 8, 16, 24...)
    for x in range(8, w - 1, 8):
        diff_v += np.sum(np.abs(image[:, x].astype(int) - image[:, x-1].astype(int)))
        count_v += h
        
    avg_h_diff = diff_h / count_h if count_h > 0 else 0
    avg_v_diff = diff_v / count_v if count_v > 0 else 0
    
    avg_block_diff = (avg_h_diff + avg_v_diff) / 2.0
    
    # In heavily manipulated images, the original 8x8 grid might be destroyed or shifted in pasted regions,
    # or re-compression might create a secondary grid.
    # If block differences are extremely low, it could be a lossless format (no risk from this test),
    # but if they are very high, it could mean heavy recompression.
    # We map avg_block_diff to a risk score heuristically.
    risk_score = min(int(avg_block_diff * 5), 100)
    
    return {
        "risk": risk_score,
        "avg_block_diff": float(avg_block_diff)
    }
