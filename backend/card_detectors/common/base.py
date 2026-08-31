import re

class CardDetector:
    def detect_card_number(self, boxes: list, full_text: str = "") -> dict:
        """
        Takes raw OCR boxes and full_text, reconstructs text, finds candidates,
        validates them, and returns the best normalized match.
        """
        raise NotImplementedError

    def reconstruct_text(self, boxes: list) -> list:
        """
        Combines split OCR bounding boxes into single logical strings based on spatial proximity.
        """
        if not boxes:
            return []
        
        # Sort boxes by center_y or y
        sorted_by_y = sorted(boxes, key=lambda b: b.get("center_y", b.get("y", 0)))
        
        lines = []
        current_line = []
        current_y = None
        
        for box in sorted_by_y:
            y = box.get("center_y", box.get("y", 0))
            if current_y is None:
                current_line.append(box)
                current_y = y
            else:
                # Use a more forgiving threshold (e.g. 35 pixels) to handle slight rotations
                if abs(y - current_y) < 35:
                    current_line.append(box)
                else:
                    lines.append(current_line)
                    current_line = [box]
                    current_y = y
        if current_line:
            lines.append(current_line)
            
        reconstructed = []
        for line in lines:
            # Sort horizontally by center_x or x
            line.sort(key=lambda b: b.get("center_x", b.get("x", 0)))
            text = " ".join([b.get("text", "") for b in line])
            # Average confidence
            conf = sum(b.get("confidence", 0) for b in line) / len(line) if line else 0
            
            x = min(b.get("x", 0) for b in line) if line else 0
            y = min(b.get("y", 0) for b in line) if line else 0
            
            reconstructed.append({
                "raw_text": text,
                "confidence": conf,
                "x": x,
                "y": y
            })
            
        return reconstructed

    def normalize(self, value: str) -> str:
        if not value:
            return None
        value = value.upper()
        # Remove whitespace and common separators
        value = re.sub(r"[\s\-\.]", "", value)
        return value
