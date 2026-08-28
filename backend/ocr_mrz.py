"""
Extract MRZ text from a document image via Tesseract OCR.

Pipeline: grayscale -> crop bottom band (MRZ sits in the bottom ~25%
of a standard passport photo page) -> threshold -> OCR with a
whitelist restricted to MRZ's actual charset (A-Z, 0-9, <).

This is intentionally the boring option: Tesseract is already
installed, already-installed dependency solves it (ladder rung 5) -
no custom OCR model needed for machine-printed monospace text.
"""

from PIL import Image, ImageOps
import pytesseract

MRZ_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
TESSERACT_CONFIG = f"--psm 6 -c tessedit_char_whitelist={MRZ_CHARSET}"


def _preprocess(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img)
    w, h = gray.size
    # MRZ lives in the bottom band of the document image
    mrz_band = gray.crop((0, int(h * 0.72), w, h))
    # simple binarization — OCR-B monospace reads cleanly off a hard threshold
    bw = mrz_band.point(lambda p: 255 if p > 140 else 0)
    return bw


def extract_mrz_lines(image_path: str) -> list[str]:
    """
    Returns the OCR'd MRZ lines (cleaned, uppercased, 44-char lines
    for TD3 passports). Caller should sanity-check line count/length
    before passing to the checksum validator.
    """
    img = Image.open(image_path)
    processed = _preprocess(img)
    raw = pytesseract.image_to_string(processed, config=TESSERACT_CONFIG)

    lines = [l.strip().upper() for l in raw.splitlines() if l.strip()]
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