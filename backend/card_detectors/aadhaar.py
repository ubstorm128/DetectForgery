import re
from .base import CardDetector

class AadhaarDetector(CardDetector):
    def normalize(self, value: str) -> str:
        val = super().normalize(value)
        if not val: return None
        
        val = re.sub(r"[^A-Z0-9]", "", val.upper())
        
        # OCR Correction for Aadhaar (all characters should be digits)
        val = val.replace("O", "0").replace("Q", "0").replace("D", "0")
        val = val.replace("I", "1").replace("L", "1")
        val = val.replace("Z", "2")
        val = val.replace("A", "4")
        val = val.replace("S", "5")
        val = val.replace("G", "6")
        val = val.replace("T", "7")
        val = val.replace("B", "8")
        
        return val

    def detect_card_number(self, boxes: list, full_text: str = "") -> dict:
        candidates = []
        
        # 1. Try on reconstructed lines first
        lines = self.reconstruct_text(boxes)
        
        # Relaxed pattern allowing letters so we can correct them in normalization
        pattern = r"\b[A-Za-z0-9]{4}[\s\-\.]*[A-Za-z0-9]{4}[\s\-\.]*[A-Za-z0-9]{4}\b"
        
        for line in lines:
            matches = re.findall(pattern, line["raw_text"])
            for match in matches:
                norm = self.normalize(match)
                if len(norm) == 12 and norm.isdigit():
                    candidates.append({
                        "raw_text": match,
                        "normalized": norm,
                        "confidence": line["confidence"]
                    })
        
        # 2. Try on full_text fallback if no candidates found on specific lines
        if not candidates and full_text:
            matches = re.findall(pattern, full_text)
            for match in matches:
                norm = self.normalize(match)
                if len(norm) == 12 and norm.isdigit():
                    candidates.append({
                        "raw_text": match,
                        "normalized": norm,
                        "confidence": 0.8  # Default fallback confidence
                    })
                    
        # 3. Ultimate fallback: Join all raw box text (bypasses redaction in main.py)
        if not candidates and boxes:
            raw_joined = " ".join([b.get("text", "") for b in boxes])
            matches = re.findall(pattern, raw_joined)
            for match in matches:
                norm = self.normalize(match)
                if len(norm) == 12 and norm.isdigit():
                    candidates.append({
                        "raw_text": match,
                        "normalized": norm,
                        "confidence": 0.75
                    })
        
        if candidates:
            # Sort by confidence
            candidates.sort(key=lambda x: x["confidence"], reverse=True)
            best = candidates[0]
            best["detected"] = True
            return best
            
        return {
            "raw_text": None,
            "normalized": None,
            "confidence": 0.0,
            "detected": False
        }
