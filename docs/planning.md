# Veristamp: AI-Based Fake Identity & Document Screening System
**PS ID:** 26188 | **Org:** Ministry of Home Affairs — SSB, Police II Division | **Theme:** Blockchain & Cybersecurity

---

## 1. Scope

**In scope**
- Screening identity documents (Passports, Aadhaar, etc.) for tampering/forgery.
- Template-driven configuration system (`backend/templates/*.json`) supporting custom fields, layouts, and validation rules for any new document type.
- OCR text extraction (Tesseract) and geometric alignment mapping.
- Visual tampering detection: Error Level Analysis (ELA), ORB Copy-Move detection, Compression analysis (DCT), Metadata checks.
- Dual-side cross-verification for smart cards (e.g. comparing Aadhaar Front vs Aadhaar Back OCR to detect spoofing).
- Explainable output dashboard: 0-100 Authenticity Score with category classification (Genuine, Suspicious, Likely Fake) + bounding boxes highlighting flagged regions.
- High privacy standards: No full sensitive IDs permanently stored in logs (automatic masking).

**Out of scope (say this explicitly to judges)**
- Visa issuance workflows or full immigration management systems.
- Replacing official UIDAI/Government API validation (this tool performs *forensic visual screening* before API pinging or for offline checks).
- Real-time camera hardware integration (demo relies on uploaded files).

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| OCR / doc extraction | Tesseract OCR | Pretrained, reliable, lightweight. |
| Configuration System | JSON Templates | Allows adding new document types without code changes. |
| Tamper/splice detection | Error Level Analysis (ELA), ORB Copy-Move (OpenCV) | Classical CV isolates splices and clones without massive GPU requirements. |
| Backend | FastAPI | Minimal boilerplate, async, auto docs. |
| Frontend | HTML/CSS/JS (SPA) | Fully responsive SaaS landing page format embedded with the screening tool; highly maintainable. No React boilerplate required. |
| Scoring Engine | Unified Python Scoring logic | Weights disparate forensic signals into an actionable 0-100 score. |

---

## 3. Architecture

```
Upload Image (Frontend SPA)
       │
       ▼
┌──────────────┐
│  FastAPI API │ (/api/analyze-image)
└──────┬───────┘
       ▼
┌─────────────────────────────────┐
│ Template Config System (JSON)   │ Load layout/rules for Aadhaar/Passport
└──────┬──────────────────────────┘
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
┌─────────────┐                   ┌─────────────┐
│  OCR & Geo   │                   │ Tamper      │
│  Extraction  │                   │ Detection   │
│ (Tesseract)  │                   │ (ELA, ORB)  │
└──────┬───────┘                   └─────┬───────┘
       │                                 │
       ▼                                 ▼
┌───────────────────────────────────────────────┐
│              Scoring & Aggregation            │ (0-100 Score)
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│            Dual-Side Cross Match              │ (/api/compare-sides)
│ (If Aadhaar front and back are both provided) │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│       Frontend Dashboard Visualization        │ (Bounding boxes, scores)
└───────────────────────────────────────────────┘
```

The system uses a completely decoupled frontend (`index.html` + `/static/`) interacting with a unified FastAPI backend. No complex service mesh needed.

---

## 4. Workflows

**Single-Sided Document (Passport):**
1. User selects "Passport", uploads image.
2. System extracts data, runs ELA/ORB.
3. System returns Authenticity Score & visual maps.

**Dual-Sided Document (Aadhaar):**
1. User selects "Aadhaar", uploads Front.
2. System detects it is the Front via heuristic checks, temporarily caches data in frontend state, prompts for Back.
3. User uploads Back. System analyzes Back.
4. Frontend triggers cross-match verification `/api/compare-sides` to ensure the text (e.g. name, UID) matches on both sides.
5. Consolidated score is presented.

---

## 5. Build & Demo Narrative

1. **The Modern Interface:** Show off the sleek Veristamp SaaS interface. Emphasize it's designed for border control agents (trust-inspiring).
2. **Standard Scan:** Upload a clean document. Show all checks passing (Genuine).
3. **The Forgery:** Upload a manipulated document (e.g. tampered photo, spliced text). Show ELA and ORB flagging the exact region, resulting in a low score (Likely Fake).
4. **The Smart Card Spoof:** Show the Aadhaar Dual-Side feature. Upload a Front, then upload a mismatched Back. The cross-match will fail, catching the spoof attempt.
5. **Privacy:** Note that no PII is retained on disk and sensitive digits are masked in the backend.

---

## 6. Team Roles

| Role | Owns |
|---|---|
| Architect / Fullstack | FastAPI routes, Frontend UI styling, state management (Dual-sided flow). |
| CV / Forensics | OpenCV integration, ELA tuning, ORB algorithms, metadata parsing. |
| OCR / Pipeline | Tesseract integration, Template configuration mappings. |
| Pitch / Product | Demo flow, slides, narrative, dataset curation. |