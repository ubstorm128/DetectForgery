import re
from .base import CardDetector

class PANDetector(CardDetector):
    def normalize(self, value: str) -> str:
        val = super().normalize(value)
        if not val:
            return None
            
        # Remove anything not alphanumeric
        val = re.sub(r"[^A-Z0-9]", "", val)
        
        # Position-aware correction logic for typical OCR mistakes
        if len(val) == 10:
            # First 5 should be letters
            first_5 = val[:5].replace("0", "O").replace("1", "I").replace("5", "S").replace("8", "B")
            # Next 4 should be numbers
            next_4 = val[5:9].replace("O", "0").replace("I", "1").replace("S", "5").replace("B", "8").replace("Z", "2").replace("G", "6")
            # Last should be letter
            last_1 = val[9:].replace("0", "O").replace("1", "I").replace("5", "S").replace("8", "B")
            val = first_5 + next_4 + last_1
            
        return val

    def detect_card_number(self, boxes: list, full_text: str = "") -> dict:
        candidates = []
        lines = self.reconstruct_text(boxes)
        
        # PAN is usually 10 characters. Allow spaces in the raw text.
        pattern = r"\b[A-Z0-9\s]{10,14}\b"
        
        for line in lines:
            # Basic alphanumeric extraction
            cleaned = re.sub(r"[^A-Z0-9]", "", line["raw_text"].upper())
            
            # PAN numbers are exactly 10 characters
            if len(cleaned) == 10:
                norm = self.normalize(cleaned)
                # Validate the normalized pattern: 5 letters, 4 digits, 1 letter
                if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", norm):
                    candidates.append({
                        "raw_text": line["raw_text"],
                        "normalized": norm,
                        "confidence": line["confidence"]
                    })
        
        # Fallback to full text if no lines matched perfectly
        if not candidates and full_text:
            # Look for 10 consecutive alphanumeric chars
            matches = re.finditer(r"[A-Z0-9\s]{10,15}", full_text.upper())
            for m in matches:
                cleaned = re.sub(r"[^A-Z0-9]", "", m.group(0))
                if len(cleaned) == 10:
                    norm = self.normalize(cleaned)
                    if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", norm):
                        candidates.append({
                            "raw_text": m.group(0),
                            "normalized": norm,
                            "confidence": 0.7  # Lower confidence for fallback
                        })
                    
        if candidates:
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
