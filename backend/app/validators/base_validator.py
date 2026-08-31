from abc import ABC, abstractmethod
import numpy as np

class DocumentValidator(ABC):
    """
    Base interface for document-specific validators.
    """
    
    @abstractmethod
    def validate(self, image: np.ndarray, ocr_result: dict, config: dict, forensic_results: dict = None) -> dict:
        """
        Validates the document against its specific rules (layout, text, security features).
        
        Args:
            image (np.ndarray): The normalized/cropped document image.
            ocr_result (dict): The extracted OCR data.
            config (dict): The document-specific JSON configuration rules.
            forensic_results (dict, optional): Results from lower-level forensic analysis.
            
        Returns:
            dict: Structured validation result including scores for layout, text, and security features.
        """
        pass
