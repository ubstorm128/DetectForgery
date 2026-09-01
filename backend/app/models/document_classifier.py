from abc import ABC, abstractmethod
import cv2
import numpy as np

class DocumentClassifier(ABC):
    """
    Base interface for document classification.
    """
    @abstractmethod
    def classify(self, cropped_image: np.ndarray) -> dict:
        """
        Classifies the cropped document image.
        
        Args:
            cropped_image (np.ndarray): The cropped BGR image of the document.
            
        Returns:
            dict: {
                "document_type": str, # e.g. "aadhaar", "pan", "unknown"
                "confidence": float
            }
        """
        pass


class YOLODocumentClassifier(DocumentClassifier):
    """
    Ultralytics YOLO implementation for Document Classification.
    """
    def __init__(self, model_path: str = None):
        self.model_path = model_path
        self.model = None
        
        # Mappings from YOLO class indices to standard system identifiers
        self.class_map = {
            0: "aadhaar",
            1: "pan",
            2: "passport",
            3: "driving_licence",
            4: "voter_id",
            5: "other_id",
            6: "unknown"
        }
        
        if self.model_path:
            try:
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
            except ImportError:
                print("Warning: ultralytics not installed. YOLODocumentClassifier will run in mock mode.")
            except Exception as e:
                print(f"Failed to load YOLO model: {e}")

    def classify(self, cropped_image: np.ndarray, filename: str = "") -> dict:
        if self.model is None:
            # --- MOCK IMPLEMENTATION (Placeholder until real weights are trained) ---
            doc_type = "aadhaar"
            filename_lower = filename.lower() if filename else getattr(cropped_image, 'filename', '').lower()
            
            if "pan" in filename_lower:
                doc_type = "pan"
            elif "passport" in filename_lower:
                doc_type = "passport"
            elif "driving" in filename_lower or "dl" in filename_lower:
                doc_type = "driving_licence"
                
            return {
                "document_type": doc_type,
                "confidence": 0.98
            }

        # --- ACTUAL YOLO INFERENCE ---
        results = self.model(cropped_image, verbose=False)
        
        if len(results) == 0:
            return {
                "document_type": "unknown",
                "confidence": 0.0
            }

        # For a classification model, results[0].probs contains probabilities
        if hasattr(results[0], "probs") and results[0].probs is not None:
            top1_idx = int(results[0].probs.top1)
            top1_conf = float(results[0].probs.top1conf)
            doc_type = self.class_map.get(top1_idx, "unknown")
            
            return {
                "document_type": doc_type,
                "confidence": round(top1_conf, 3)
            }
            
        # Fallback if using a detection model for classification
        elif hasattr(results[0], "boxes") and len(results[0].boxes) > 0:
            best_box = None
            best_conf = 0.0
            
            for box in results[0].boxes:
                conf = float(box.conf[0])
                if conf > best_conf:
                    best_conf = conf
                    best_box = box
                    
            if best_box is not None:
                cls_idx = int(best_box.cls[0])
                return {
                    "document_type": self.class_map.get(cls_idx, "unknown"),
                    "confidence": round(best_conf, 3)
                }

        return {
            "document_type": "unknown",
            "confidence": 0.0
        }
