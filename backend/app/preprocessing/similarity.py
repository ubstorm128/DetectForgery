"""
Structural Similarity and Feature Analysis Service
Provides SSIM on normalized geometry, Canny edge structure analysis, and feature matching.
"""

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


def compute_structural_ssim(
    image1_gray: np.ndarray,
    image2_gray: np.ndarray
) -> tuple[float, np.ndarray]:
    """
    Compute SSIM after dimension standardization and normalization.
    Returns SSIM score (0.0 to 1.0) and difference map.
    """
    if image1_gray is None or image2_gray is None:
        return 0.0, np.zeros((100, 100), dtype=np.uint8)

    h, w = image2_gray.shape[:2]
    # Resize image1 to match image2 standard shape
    if image1_gray.shape[:2] != (h, w):
        image1_resized = cv2.resize(image1_gray, (w, h), interpolation=cv2.INTER_AREA)
    else:
        image1_resized = image1_gray

    # Smooth mild capture/sensor differences
    img1_smooth = cv2.GaussianBlur(image1_resized, (5, 5), 0)
    img2_smooth = cv2.GaussianBlur(image2_gray, (5, 5), 0)

    score, diff = ssim(img1_smooth, img2_smooth, full=True)
    diff = (diff * 255).astype("uint8")
    return float(score), diff


def compare_structural_edges(
    image1_gray: np.ndarray,
    image2_gray: np.ndarray,
    canny_thresh1: int = 50,
    canny_thresh2: int = 150
) -> dict:
    """
    Compare major structural edges (borders, photos, header boundaries, logos)
    using Canny edge maps, ignoring fine sensor noise.
    """
    if image1_gray is None or image2_gray is None:
        return {"edge_similarity": 0.0, "score": 0}

    h, w = image2_gray.shape[:2]
    img1_resized = cv2.resize(image1_gray, (w, h), interpolation=cv2.INTER_AREA)

    # Mild blur before edge detection to suppress noise
    b1 = cv2.GaussianBlur(img1_resized, (3, 3), 0)
    b2 = cv2.GaussianBlur(image2_gray, (3, 3), 0)

    edges1 = cv2.Canny(b1, canny_thresh1, canny_thresh2)
    edges2 = cv2.Canny(b2, canny_thresh1, canny_thresh2)

    # Dilate edges slightly to tolerate small sub-pixel photography shifts
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated1 = cv2.dilate(edges1, kernel, iterations=1)
    dilated2 = cv2.dilate(edges2, kernel, iterations=1)

    # Intersection over Union (IoU) of structural edges
    intersection = np.logical_and(dilated1 > 0, dilated2 > 0).sum()
    union = np.logical_or(dilated1 > 0, dilated2 > 0).sum()

    iou = float(intersection / union) if union > 0 else 0.0
    # Map edge IoU to a calibrated 0-100 score
    if iou >= 0.35:
        edge_score = 100
    elif iou >= 0.20:
        edge_score = 75 + (iou - 0.20) / 0.15 * 25
    elif iou >= 0.10:
        edge_score = 50 + (iou - 0.10) / 0.10 * 25
    else:
        edge_score = max(20, iou / 0.10 * 50)

    return {
        "edge_similarity": round(iou, 4),
        "score": int(round(edge_score))
    }


def compute_feature_match_score(
    image1_gray: np.ndarray,
    image2_gray: np.ndarray
) -> dict:
    """
    Computes keypoint feature matching (ORB/SIFT) to verify document structural presence.
    """
    if image1_gray is None or image2_gray is None:
        return {"status": "failed", "score": 0, "good_matches": 0}

    orb = cv2.ORB_create(nfeatures=2000)
    kp1, des1 = orb.detectAndCompute(image1_gray, None)
    kp2, des2 = orb.detectAndCompute(image2_gray, None)

    if des1 is None or des2 is None or len(kp1) < 5 or len(kp2) < 5:
        return {"status": "insufficient_features", "score": 50, "good_matches": 0}

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(des1, des2, k=2)

    good_matches = []
    for m_tuple in matches:
        if len(m_tuple) == 2:
            m, n = m_tuple
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)

    n_good = len(good_matches)
    if n_good >= 50:
        score = 100
    elif n_good >= 25:
        score = 80 + (n_good - 25) / 25 * 20
    elif n_good >= 10:
        score = 60 + (n_good - 10) / 15 * 20
    else:
        score = max(20, n_good / 10 * 60)

    return {
        "status": "success",
        "good_matches": n_good,
        "score": int(round(score))
    }
