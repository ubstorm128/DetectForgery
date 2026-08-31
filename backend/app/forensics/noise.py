"""
Noise Analysis
Analyzes local noise characteristics across the image. 
Different noise levels or unnaturally smooth regions can indicate blurring or copy-pasting.
"""
import cv2
import numpy as np
import os

def perform_noise_analysis(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {"risk": 0, "error": "File not found"}
        
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return {"risk": 0, "error": "Could not read image for noise analysis"}
        
    # Apply median blur to estimate the "clean" image
    blurred = cv2.medianBlur(image, 5)
    
    # The noise residual is the difference between original and blurred
    noise = cv2.absdiff(image, blurred)
    
    # Calculate local variance of noise in 16x16 blocks
    h, w = noise.shape
    block_size = 16
    variances = []
    
    for y in range(0, h, block_size):
        for x in range(0, w, block_size):
            block = noise[y:y+block_size, x:x+block_size]
            if block.size > 0:
                variances.append(np.var(block))
                
    if not variances:
        return {"risk": 0, "error": "Could not calculate variances"}
        
    # If the standard deviation of local noise variances is high, 
    # it means some areas are very noisy and some are unnaturally smooth.
    noise_variance_std = np.std(variances)
    
    # Heuristic scoring
    risk_score = min(int(noise_variance_std / 2.0), 100)
    
    return {
        "risk": risk_score,
        "noise_variance_std": float(noise_variance_std)
    }
