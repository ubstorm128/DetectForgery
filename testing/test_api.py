import requests
import sys

url = "http://127.0.0.1:8000/api/verify"
image_path = r"e:\SIH 2026\DetectForgery\Picsart_26-08-31_01-39-20-710.jpg"

try:
    with open(image_path, "rb") as f:
        files = {"file": f}
        data = {"expected_type": "auto"}
        print(f"Sending POST request to {url}...")
        response = requests.post(url, files=files, data=data)
        
        print(f"Status Code: {response.status_code}")
        try:
            print("Response JSON:")
            import json
            print(json.dumps(response.json(), indent=2))
        except:
            print("Response Text:")
            print(response.text)
except Exception as e:
    print(f"Error: {e}")
