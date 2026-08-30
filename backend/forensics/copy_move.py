"""
Copy-Move Detection
Uses ORB features to find duplicated regions within the same image.
"""
import cv2
import numpy as np
import os

def perform_copy_move_detection(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {"risk": 0, "matches": 0, "error": "File not found"}
        
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return {"risk": 0, "matches": 0, "error": "Could not read image"}
        
    # Resize image if too large to speed up processing
    max_dim = 800
    h, w = image.shape
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        image = cv2.resize(image, (int(w*scale), int(h*scale)))
        
    orb = cv2.ORB_create(nfeatures=2000)
    keypoints, descriptors = orb.detectAndCompute(image, None)
    
    if descriptors is None or len(descriptors) < 2:
        return {"risk": 0, "matches": 0, "error": "Not enough features detected"}
        
    # Brute-force matcher
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    
    # KNN match to find the two best matches for each descriptor (itself, and its closest duplicate)
    matches = bf.knnMatch(descriptors, descriptors, k=2)
    
    good_matches = []
    # min_dist ensures we don't match features that are physically right next to each other
    min_dist_px = 50 
    
    for m in matches:
        if len(m) == 2:
            m1, m2 = m
            # We skip self-matches by checking if m2 has a different trainIdx.
            # Usually m1 is the self-match (distance 0), m2 is the next best.
            # Actually knnMatch against the same descriptors will always have distance 0 as the first match.
            if m2.distance < 50: # ORB distance threshold
                pt1 = keypoints[m1.queryIdx].pt
                pt2 = keypoints[m2.trainIdx].pt
                # Calculate physical distance
                dist = np.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)
                if dist > min_dist_px:
                    good_matches.append(m2)
                    
    num_matches = len(good_matches)
    
    # Score heuristically based on the number of suspicious non-local matches
    # Usually a few accidental matches happen, but >10 is very suspicious.
    risk_score = min(num_matches * 5, 100)
    
    return {
        "risk": risk_score,
        "matches": num_matches
    }
