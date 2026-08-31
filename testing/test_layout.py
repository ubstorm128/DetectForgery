import sys
import os
sys.path.append(r"e:\SIH 2026\DetectForgery\backend")

from app.forensics.layout_analysis import perform_layout_analysis
import json

image_path = r"e:\SIH 2026\DetectForgery\Picsart_26-08-31_01-39-20-710.jpg"

print("Starting layout analysis...")
try:
    result = perform_layout_analysis(image_path)
    print("\n--- RESULTS ---")
    print(json.dumps(result, indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()
