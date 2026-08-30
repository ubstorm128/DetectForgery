"""
Template Alignment
Handles aligning an uploaded image to a known reference template using ORB/SIFT.
"""
import cv2
import numpy as np
import os
import json

def load_configuration(config_path: str) -> dict:
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r") as f:
        return json.load(f)

def align_image(image_path: str, reference_path: str) -> tuple[np.ndarray, dict]:
    """
    Attempts to align the input image to the reference image.
    Returns the aligned image and alignment status.
    """
    if not os.path.exists(image_path) or not os.path.exists(reference_path):
        return None, {"status": "failed", "error": "Images not found"}
        
    img = cv2.imread(image_path)
    ref = cv2.imread(reference_path)
    
    if img is None or ref is None:
        return None, {"status": "failed", "error": "Could not read images"}
        
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    
    # ORB detector
    orb = cv2.ORB_create(5000)
    keypoints1, descriptors1 = orb.detectAndCompute(img_gray, None)
    keypoints2, descriptors2 = orb.detectAndCompute(ref_gray, None)
    
    if descriptors1 is None or descriptors2 is None:
        return img, {"status": "skipped", "error": "No features found"}
        
    # Match features
    matcher = cv2.DescriptorMatcher_create(cv2.DESCRIPTOR_MATCHER_BRUTEFORCE_HAMMING)
    matches = matcher.match(descriptors1, descriptors2, None)
    
    # Sort matches by score
    matches.sort(key=lambda x: x.distance, reverse=False)
    
    # Remove not so good matches
    numGoodMatches = int(len(matches) * 0.15)
    if numGoodMatches < 10:
        return img, {"status": "skipped", "error": "Not enough good matches"}
        
    matches = matches[:numGoodMatches]
    
    # Extract location of good matches
    points1 = np.zeros((len(matches), 2), dtype=np.float32)
    points2 = np.zeros((len(matches), 2), dtype=np.float32)
    
    for i, match in enumerate(matches):
        points1[i, :] = keypoints1[match.queryIdx].pt
        points2[i, :] = keypoints2[match.trainIdx].pt
        
    # Find homography
    h, mask = cv2.findHomography(points1, points2, cv2.RANSAC)
    
    if h is None:
        return img, {"status": "skipped", "error": "Homography failed"}
        
    # Use homography
    height, width, channels = ref.shape
    im1Reg = cv2.warpPerspective(img, h, (width, height))
    
    return im1Reg, {"status": "success"}
