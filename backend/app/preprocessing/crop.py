import cv2
import numpy as np

def crop_to_bounding_box(image: np.ndarray, bbox: dict) -> np.ndarray:
    """
    Crops the image to the specified bounding box.
    
    Args:
        image (np.ndarray): The raw image.
        bbox (dict): Bounding box with 'x', 'y', 'width', 'height'.
        
    Returns:
        np.ndarray: The cropped image.
    """
    if not bbox:
        return image
        
    h, w = image.shape[:2]
    
    x = max(0, int(bbox.get("x", 0)))
    y = max(0, int(bbox.get("y", 0)))
    width = min(w - x, int(bbox.get("width", w)))
    height = min(h - y, int(bbox.get("height", h)))
    
    if width <= 0 or height <= 0:
        return image
        
    return image[y:y+height, x:x+width]
