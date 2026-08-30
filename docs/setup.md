# Veristamp Setup

Covers running the Veristamp document screening system locally on Windows.

## Prerequisites

- Python 3.10+
- Tesseract OCR (system-level, not just the Python wrapper)
  - Windows: install from https://github.com/UB-Mannheim/tesseract/wiki, then make sure `tesseract.exe` is on PATH
  - Verify with: `tesseract --version`

## Install dependencies

Run from the `backend/` folder:

```powershell
python -m pip install fastapi uvicorn pytesseract pillow python-multipart opencv-python
```

Use `python -m pip` (not bare `pip`) — guarantees packages install into the same Python that will run the server. Mismatched environments are the most common cause of "module not found" errors later.

## Run the server

```powershell
cd "e:\SIH 2026\DetectForgery\backend"
python -m uvicorn main:app --reload
```

Use `python -m uvicorn` instead of the bare `uvicorn` command — on Windows, pip-installed script shims often aren't on PATH even when the package itself is installed correctly. `python -m` sidesteps that by invoking it through the interpreter directly.

## Usage

1. **Frontend App**: Open `http://127.0.0.1:8000/` in your browser. This will load the Veristamp unified SaaS landing page and screening tool.
2. **API Docs**: Open `http://127.0.0.1:8000/docs` to see FastAPI's auto-generated interactive UI.

## Endpoints

- `POST /api/analyze-image`: Upload an image and a document type (e.g. `passport`, `aadhaar`) to run ELA, ORB Copy-Move, and OCR analysis.
- `POST /api/compare-sides`: Used for dual-sided documents like Aadhaar. Accepts front and back OCR text and scores to perform a cross-match verification.
- `GET /api/templates`: Lists available document templates from `backend/templates/`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `uvicorn: command not found` | Scripts folder not on PATH | Use `python -m uvicorn main:app --reload` |
| UI missing styles | Incorrect path to static files | Ensure `index.html` is in the root directory and `static/styles.css` is intact. |
| `ModuleNotFoundError` | `pip install` and `python` are different environments | Re-run install with `python -m pip install ...`, not bare `pip install ...` |
| Tesseract errors (`TesseractNotFoundError`) | Tesseract binary not on PATH | Confirm `tesseract --version` works in the same terminal |