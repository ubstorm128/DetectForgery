"""
Extract MRZ text from a document image via PaddleOCR.

Pipeline: grayscale -> crop bottom band (MRZ sits in the bottom ~25%
of a standard passport photo page) -> OCR -> filter for MRZ characters.
"""

import cv2
import numpy as np
from PIL import Image, ImageOps
import re
from services.ocr_service import get_paddle_ocr

MRZ_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"


def _preprocess(img_path: str) -> np.ndarray:
    img = Image.open(img_path)
    gray = ImageOps.grayscale(img)
    w, h = gray.size
    # MRZ lives in the bottom band of the document image
    mrz_band = gray.crop((0, int(h * 0.72), w, h))
    
    # Convert PIL to cv2 BGR format for PaddleOCR
    open_cv_image = np.array(mrz_band)
    if len(open_cv_image.shape) == 2:
        open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_GRAY2BGR)
        
    return open_cv_image


def extract_mrz_lines(image_path: str) -> list[str]:
    """
    Returns the OCR'd MRZ lines (cleaned, uppercased, 44-char lines
    for TD3 passports). Caller should sanity-check line count/length
    before passing to the checksum validator.
    """
    processed_bgr = _preprocess(image_path)
    
    paddle_engine = get_paddle_ocr()
    if paddle_engine is None:
        return []
        
    results = paddle_engine.ocr(processed_bgr, cls=False)
    
    lines = []
    if results and len(results) > 0 and results[0] is not None:
        for line in results[0]:
            coords, (txt, conf) = line
            # Clean text: keep only valid MRZ characters
            txt_clean = "".join([c for c in txt.upper() if c in MRZ_CHARSET])
            if txt_clean:
                lines.append(txt_clean)
                
    return lines


def demo():
    """
    Self-check: render a synthetic MRZ image (since no real sample is
    available here) and confirm OCR recovers text closely enough to
    prove the pipeline works. Swap in a real scanned passport image
    to validate against actual data.
    """
    from PIL import ImageDraw, ImageFont
    import difflib

    line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<<"
    line2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"

    # simulate a full passport page (MRZ occupies the bottom ~25%),
    # not just a cropped MRZ strip
    img = Image.new("L", (900, 600), 255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 500), line1, font=font, fill=0)
    draw.text((20, 545), line2, font=font, fill=0)

    tmp_path = "/tmp/synthetic_mrz.png"
    img.save(tmp_path)

    lines = extract_mrz_lines(tmp_path)
    print("OCR output:", lines)

    assert len(lines) >= 2, f"expected 2 MRZ lines, got {lines}"
    similarity = difflib.SequenceMatcher(None, lines[-1], line2).ratio()
    print(f"Line 2 similarity to ground truth: {similarity:.2%}")
    assert similarity > 0.9, "OCR quality too low — check font/preprocessing"
    print("OCR pipeline self-check: PASS")


if __name__ == "__main__":
    demo()