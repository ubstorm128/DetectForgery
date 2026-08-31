import sys
sys.path.append(r"e:\SIH 2026\DetectForgery\backend")
from app.ocr.paddleocr_engine import extract_ocr_data
image_path = r"e:\SIH 2026\DetectForgery\Picsart_26-08-31_01-39-20-710.jpg"
print("Calling extract_ocr_data...")
res = extract_ocr_data(image_path)
print("Done extracting!")
