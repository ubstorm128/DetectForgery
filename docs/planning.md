# Veristamp: AI-Based Fake Identity & Document Screening System (v3)
**PS ID:** 26188 | **Org:** Ministry of Home Affairs — SSB, Police II Division | **Theme:** Blockchain & Cybersecurity

---

## 1. Scope

**In scope**
- Automated identity document detection and classification via YOLO models.
- Deep OCR text extraction and spatial coordinate mapping using PaddleOCR.
- Layout and geometry heuristics to detect typographical offsets, spacing errors, and scaling anomalies without requiring Neural Network training.
- Visual tampering detection: Error Level Analysis (ELA), ORB Copy-Move detection, noise variance, and Metadata checks.
- Explainable output dashboard: 0-100 Authenticity Score with category classification (Genuine, Suspicious, Likely Fake) + bounding boxes highlighting flagged layout regions.
- High privacy standards: No full sensitive IDs permanently stored in logs (automatic masking capability).

**Out of scope (say this explicitly to judges)**
- Visa issuance workflows or full immigration management systems.
- Replacing official UIDAI/Government API validation (this tool performs *forensic visual screening* before API pinging or for offline checks).
- Real-time camera hardware integration (demo relies on uploaded files).

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Classification & Cropping | Ultralytics YOLO | High-speed detection of document boundaries and type classification. |
| OCR / Text extraction | PaddleOCR | Highly accurate multilingual support (Hindi/English) and precise spatial bounding boxes. |
| Validation Rules | Deterministic Heuristics | Spatial coordinate rules (`layout_analysis.py`) avoid black-box ML bias. |
| Tamper/splice detection | Error Level Analysis (ELA), ORB Copy-Move | Classical CV isolates splices and clones without massive GPU requirements. |
| Backend | FastAPI | Minimal boilerplate, async, auto docs. Serves both the REST API and the static frontend. |
| Frontend | HTML/CSS/JS (Vanilla) | Fully responsive SaaS landing page format embedded with the screening tool; highly maintainable. |

---

## 3. Architecture

```
Upload Image (Frontend SPA)
       │
       ▼
┌──────────────┐
│  FastAPI API │ (POST /api/verify)
└──────┬───────┘
       ▼
┌─────────────────────────────────┐
│ AI Detection & Classification   │ (YOLO Models)
└──────┬──────────────────────────┘
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
┌─────────────┐                   ┌─────────────┐
│  PaddleOCR  │                   │ Tamper      │
│  Extraction │                   │ Detection   │
│ & Layout    │                   │ (ELA, ORB)  │
└──────┬───────┘                   └─────┬───────┘
       │                                 │
       ▼                                 ▼
┌───────────────────────────────────────────────┐
│              Scoring & Aggregation            │ (0-100 Score)
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│       Frontend Dashboard Visualization        │ (Bounding boxes, visual dashboard)
└───────────────────────────────────────────────┘
```

The system uses a tightly coupled but cleanly separated frontend (`index.html` + `script.js`) interacting with a unified FastAPI backend that mounts the static files alongside the `/api` routes. 

---

## 4. Workflows

**Single-Sided Document (Aadhaar / Passport):**
1. User uploads the image.
2. The `POST /api/verify` pipeline executes:
   - **YOLO:** Detects the document and crops it.
   - **YOLO:** Classifies the document type (e.g. Aadhaar vs PAN).
   - **Pre-processing:** Image quality assessment and perspective correction.
   - **PaddleOCR:** Extracts Hindi/English text and exact geometry.
   - **Layout Analysis:** Checks coordinates against authentic templates.
   - **Forensics:** Checks for ELA and ORB copy-move manipulation.
3. System aggregates the components into a `final_score` (0-100) and assigns a status (`likely_valid`, `suspicious`, `likely_fake`).
4. Frontend visualizes the score, detailed breakdown, and exact explainable reasons.

---

## 5. Build & Demo Narrative

1. **The Modern Interface:** Show off the sleek Veristamp SaaS interface. Emphasize it's designed for quick security checks.
2. **Standard Scan:** Upload a clean document. Show all checks passing (Genuine).
3. **The Forgery:** Upload a manipulated document (e.g. tampered text, layout shifting). Show the layout spatial rules catching the offset and flagging the exact region, resulting in a low score (Likely Fake).
4. **Transparency:** Point out the "Explainable Reasoning" list that proves the system isn't just a black box guessing.
5. **Privacy:** Note that no PII is retained on disk after analysis completes.