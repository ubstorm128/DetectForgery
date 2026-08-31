import sys
import cv2
import numpy as np

sys.path.append(r"e:\SIH 2026\DetectForgery\backend")

from app.preprocessing.quality import assess_image_quality
from app.forensics.ela import perform_ela
from app.forensics.noise import perform_noise_analysis
from app.forensics.copy_move import perform_copy_move_detection

image_path = r"e:\SIH 2026\DetectForgery\Picsart_26-08-31_01-39-20-710.jpg"
raw_img = cv2.imread(image_path)

print("Testing assess_image_quality...")
q = assess_image_quality(raw_img)
print(q)

print("Testing perform_ela...")
e = perform_ela(raw_img)
print(e)

print("Testing perform_noise_analysis...")
n = perform_noise_analysis(raw_img)
print(n)

print("Testing perform_copy_move_detection...")
c = perform_copy_move_detection(raw_img)
print(c)

print("ALL TESTS PASSED WITHOUT CRASHING")
