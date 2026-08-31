import cv2
from paddleocr import PaddleOCR

def preprocess_for_ocr(img_bgr):
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l_channel)
    limg = cv2.merge((cl, a_channel, b_channel))
    enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    gaussian = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
    sharpened = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
    return sharpened

img = cv2.imread(r'e:\SIH 2026\DetectForgery\Picsart_26-08-31_01-39-20-710.jpg')
print("Image loaded, preprocessing...")
processed_img = preprocess_for_ocr(img)
print("Preprocessing done. Init OCR...")
ocr = PaddleOCR(use_angle_cls=False, lang='hi', enable_mkldnn=False)
print("OCR init done. Running OCR...")
res = ocr.ocr(processed_img)
print("SUCCESS!")
