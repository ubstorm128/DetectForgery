from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os

from app.api.routes_verify import router as verify_router

app = FastAPI(
    title="Hybrid AI Document Verification API",
    description="Automated AI document detection, classification, OCR, and forensic verification.",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(verify_router)

def get_static_path(filename: str) -> str:
    # Serve from the root 'DetectForgery' directory
    dev_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", filename))
    if os.path.exists(dev_path):
        return dev_path
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", filename))

@app.get("/")
@app.get("/index.html")
async def root():
    path = get_static_path("index.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Index page not found"}

@app.get("/scanner.html")
async def scanner():
    path = get_static_path("scanner.html")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Scanner page not found"}

@app.get("/styles.css")
async def styles():
    path = get_static_path("styles.css")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Styles not found"}

@app.get("/script.js")
async def script():
    path = get_static_path("script.js")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Script not found"}

@app.get("/ficon.png")
async def ficon():
    path = get_static_path("ficon.png")
    if os.path.exists(path):
        return FileResponse(path)
    return {"error": "Favicon not found"}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}
