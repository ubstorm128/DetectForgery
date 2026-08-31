"""
Copy-Move Detection
Uses SIFT/ORB features and RANSAC to find geometrically consistent duplicated regions,
minimizing false positives from naturally repeated document textures.
"""
import cv2
import numpy as np
import os

MIN_GOOD_MATCHES = 10
MIN_INLIER_MATCHES = 8
MIN_SPATIAL_SEPARATION_PX = 50

def perform_copy_move_detection(image_path: str) -> dict:
    if not os.path.exists(image_path):
        return {"risk": 0, "integrity": 100, "matches": 0, "error": "File not found"}
        
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        return {"risk": 0, "integrity": 100, "matches": 0, "error": "Could not read image"}
        
    # Resize image if too large to speed up processing
    max_dim = 1000
    h, w = image.shape
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        image = cv2.resize(image, (int(w*scale), int(h*scale)))
        
    # Try SIFT first, fallback to ORB
    try:
        detector = cv2.SIFT_create()
        norm_type = cv2.NORM_L2
    except Exception:
        detector = cv2.ORB_create(nfeatures=3000)
        norm_type = cv2.NORM_HAMMING

    keypoints, descriptors = detector.detectAndCompute(image, None)
    
    if descriptors is None or len(descriptors) < MIN_GOOD_MATCHES:
        return {"risk": 0, "integrity": 100, "matches": 0, "error": "Not enough features detected"}
        
    # Brute-force matcher
    bf = cv2.BFMatcher(norm_type, crossCheck=False)
    
    # KNN match to find the two best matches for each descriptor
    # m[0] is typically the self-match (distance 0), m[1] is the best actual match elsewhere
    try:
        matches = bf.knnMatch(descriptors, descriptors, k=2)
    except Exception as e:
        return {"risk": 0, "integrity": 100, "matches": 0, "error": f"Matching failed: {str(e)}"}
    
    good_matches = []
    
    for m in matches:
        if len(m) == 2:
            m1, m2 = m
            # Check if m2 is a distinct feature (not essentially the same point)
            pt1 = keypoints[m1.queryIdx].pt
            pt2 = keypoints[m2.trainIdx].pt
            
            # Calculate physical distance
            dist = np.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)
            
            # Require spatial separation (ignore self-matches or very close neighboring pixels)
            if dist > MIN_SPATIAL_SEPARATION_PX:
                good_matches.append(m2)
                    
    num_good = len(good_matches)
    if num_good < MIN_GOOD_MATCHES:
        return {"risk": 0, "integrity": 100, "matches": num_good}

    # Extract location of good matches
    src_pts = np.float32([keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    # Use RANSAC to find geometrically consistent clusters of matching points
    try:
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    except Exception:
        mask = None

    if mask is None:
        inliers_count = 0
    else:
        inliers_count = int(np.sum(mask))

    if inliers_count < MIN_INLIER_MATCHES:
        return {"risk": 0, "integrity": 100, "matches": inliers_count, "note": "Insufficient geometric consistency"}

    # Calculate the bounding box of the inlier matched points in the destination region
    inlier_dst_pts = dst_pts[mask.ravel() == 1]
    
    if len(inlier_dst_pts) > 0:
        x, y, w_box, h_box = cv2.boundingRect(inlier_dst_pts)
        suspicious_area = w_box * h_box
        total_area = w * h
        suspicious_area_ratio = suspicious_area / total_area if total_area > 0 else 0
    else:
        suspicious_area_ratio = 0

    # Score based on the size of the duplicated region relative to the document
    if suspicious_area_ratio < 0.01:
        risk_score = 0
    elif suspicious_area_ratio < 0.03:
        risk_score = 10
    elif suspicious_area_ratio < 0.08:
        risk_score = 40
    else:
        # Cap at 80 so it doesn't instantly fail an otherwise perfect card
        risk_score = 80
        
    integrity_score = 100 - risk_score
    
    return {
        "risk": risk_score,
        "integrity": integrity_score,
        "matches": inliers_count,
        "total_good_matches": num_good,
        "suspicious_area_ratio": round(suspicious_area_ratio, 4)
    }

