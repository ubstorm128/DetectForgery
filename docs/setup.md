# Backend Setup

Covers running the document screening API (`backend/`) locally on Windows.

## Prerequisites

- Python 3.10+
- Tesseract OCR (system-level, not just the Python wrapper)
  - Windows: install from https://github.com/UB-Mannheim/tesseract/wiki, then make sure `tesseract.exe` is on PATH
  - Verify with: `tesseract --version`

## Install dependencies

Run from the `backend/` folder:

```powershell
python -m pip install fastapi uvicorn pytesseract pillow python-multipart
```

Use `python -m pip` (not bare `pip`) — guarantees packages install into the same Python that will run the server. Mismatched environments are the most common cause of "module not found" errors later.

## Run the server

```powershell
cd D:\PLACE\DetectForgery\backend
python -m uvicorn main:app --reload
```

Use `python -m uvicorn` instead of the bare `uvicorn` command — on Windows, pip-installed script shims often aren't on PATH even when the package itself is installed correctly. `python -m` sidesteps that by invoking it through the interpreter directly.

Server runs at `http://127.0.0.1:8000`.

## Test it

1. Open `http://127.0.0.1:8000/docs` — FastAPI's auto-generated interactive UI.
2. Expand **POST /screen** → click **Try it out**.
3. Upload a document image → **Execute**.
4. Check the response:
   - `raw_ocr_lines` — what Tesseract actually read off the image. Two 44-character lines expected for a passport (TD3 format).
   - `screening_result.valid` — overall pass/fail.
   - `screening_result.checks` — per-field breakdown (which check digit matched/failed), not just a score.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `uvicorn: command not found` | Scripts folder not on PATH | Use `python -m uvicorn main:app --reload` |
| `422` with garbled `raw_ocr_lines` | OCR isn't finding a clean 44-char MRZ line | Check image is right-side-up, MRZ visible in bottom ~25% of frame; may need to tune the crop band in `ocr_mrz.py` |
| `ModuleNotFoundError` | `pip install` and `python` are different environments | Re-run install with `python -m pip install ...`, not bare `pip install ...` |
| Tesseract errors (`TesseractNotFoundError`) | Tesseract binary not on PATH | Confirm `tesseract --version` works in the same terminal |