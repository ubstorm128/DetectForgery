# Veristamp Setup (v3.0.0)

Covers running the Veristamp AI Document Screening system locally on Windows.

## Prerequisites

- Python 3.10+
- Microsoft Visual C++ Redistributable (Required for PaddleOCR and OpenCV)

## Install dependencies

Run from the `backend/` folder:

```powershell
python -m pip install fastapi uvicorn pillow python-multipart opencv-python ultralytics paddleocr paddlepaddle
```

Use `python -m pip` (not bare `pip`) — guarantees packages install into the same Python that will run the server. Mismatched environments are the most common cause of "module not found" errors later.

## Run the server

The easiest way to run the server and automatically launch the website is to double-click the `start.bat` file in the root directory.

Alternatively, you can run it manually via PowerShell:
```powershell
cd "e:\SIH 2026\DetectForgery\backend"
python -m uvicorn app.main:app --reload
```

## Usage

1. **Frontend App**: Open `http://127.0.0.1:8000/` in your browser. This will load the Veristamp unified SaaS landing page and screening tool.
2. **API Docs**: Open `http://127.0.0.1:8000/docs` to see FastAPI's auto-generated interactive UI.

## Endpoints

- `POST /api/verify`: Upload an image to run YOLO detection/classification, layout analysis, PaddleOCR text extraction, ELA, ORB Copy-Move, and noise analysis. Returns a consolidated 0-100 authenticity score.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Server completely crashes (silent exit code 1) during analysis | PaddleOCR Out-of-Memory (OOM) | High-resolution images upscaled by 2x cause C++ segfaults. Ensure the image width/height check (`max(h,w) < 1200`) in `paddleocr_engine.py` is intact. |
| `uvicorn: command not found` | Scripts folder not on PATH | Use `python -m uvicorn app.main:app --reload` |
| UI missing styles | Incorrect path to static files | Ensure `start.bat` sets the working directory correctly using `cd /d "%~dp0"`. |
| YOLO mock mode warning | Missing weights | YOLO models are currently running in mock fallback mode (`model_path=None`). Train and provide weights for production. |