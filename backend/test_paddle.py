import traceback
try:
    from paddleocr import PaddleOCR
    print("PaddleOCR imported successfully.")
    
    ocr = PaddleOCR(use_angle_cls=True, lang="en")
    print("PaddleOCR instantiated successfully.")
    print("SUCCESS")
except Exception as e:
    print("Failed to initialize PaddleOCR:")
    traceback.print_exc()
