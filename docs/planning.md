# AI-Based Fake Identity & Document Screening System
**PS ID:** 26188 | **Org:** Ministry of Home Affairs — SSB, Police II Division | **Theme:** Blockchain & Cybersecurity

---

## 1. Scope

**In scope**
- Screening passports and visas for tampering/forgery
- MRZ (Machine Readable Zone) validation against ICAO 9303 checksum standard
- Cross-field consistency checks (DOB, dates, validity windows)
- Photo tamper/splice detection
- Multi-identity detection via face similarity against a blacklist
- Explainable flag output (what failed, not just a score)

**Out of scope (say this explicitly to judges)**
- Visa issuance workflow
- Full border management / immigration system
- Multi-role admin panels, user login systems
- Real-time camera/hardware integration (demo uses uploaded images)
- Training custom OCR/face models from scratch

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| OCR / doc extraction | Tesseract OCR (MRZ mode) or PaddleOCR | Pretrained, no training needed |
| MRZ parsing | `mrz` or `passporteye` (Python) | Handles ICAO 9303 checksum logic out of the box |
| Face detection/embedding | `face_recognition` (dlib) or `InsightFace` | Pretrained embeddings, cosine similarity is enough |
| Rule engine | Plain Python | Checksum/date logic is deterministic — no ML needed |
| Tamper/splice detection | Error Level Analysis (ELA) via Pillow, or a pretrained forgery-detection model (CASIA-based) | Classical CV first, ML only if ELA insufficient |
| Backend | FastAPI | Minimal boilerplate, async, auto docs |
| Frontend | React (Vite) or plain HTML/JS | Single upload form + flag results, nothing fancier |
| Blacklist DB | SQLite | No need for Postgres at hackathon scale |
| Dataset | MIDV-500 / MIDV-2020 (synthetic ID docs) + self-edited tampered samples | Real passports are PII, can't use them |

Skipped: microservices, Kubernetes, cloud GPU training, blockchain (despite the theme tag — don't force blockchain in where it adds no function; mention it only if you have a real audit-trail use case for it).

---

## 3. Architecture

```
Upload (image) 
      │
      ▼
┌─────────────┐
│  Extraction  │  OCR → MRZ text + visual zone fields
└─────┬───────┘
      ▼
┌─────────────┐     ┌──────────────────┐
│ Rule Engine  │────▶│ Checks:          │
│ (Python)     │     │ - MRZ checksum   │
│              │     │ - date logic     │
│              │     │ - field match    │
└─────┬───────┘     └──────────────────┘
      ▼
┌─────────────┐     ┌──────────────────┐
│ Photo/Tamper │────▶│ ELA / forgery    │
│ Analysis     │     │ score            │
└─────┬───────┘     └──────────────────┘
      ▼
┌─────────────┐     ┌──────────────────┐
│ Face Match   │────▶│ Embed → compare  │
│              │     │ vs blacklist DB  │
└─────┬───────┘     └──────────────────┘
      ▼
┌─────────────────────────┐
│ Explainable Flag Output │  "MRZ checksum fail line 2"
│                          │  "Face match: 0.91 sim to entry #12"
└─────────────────────────┘
```

One backend service, one frontend, one SQLite DB. No inter-service network calls needed — everything can run in-process.

---

## 4. Dataset Plan

1. Pull MIDV-500/MIDV-2020 for clean synthetic ID samples.
2. Generate tampered negatives yourself: edit DOB/photo/visa stamp on template images (GIMP or PIL script) — label these as ground-truth fakes.
3. Build a small mock blacklist (10–20 face embeddings) for the multi-identity demo.
4. Do this before writing detection logic — it defines what fields/formats you're actually parsing.

---

## 5. Build Order (always demoable)

1. MRZ checksum validator on clean sample — standalone win, day one.
2. Run same validator on tampered sample — core "wow" moment.
3. Add ELA-based photo tamper check.
4. Add face similarity + blacklist match — second "wow" moment.
5. Wire into FastAPI backend with one `/screen` endpoint.
6. Build minimal upload UI last.

---

## 6. Validation Plan

- Test set: N clean + N tampered samples (aim for at least 20 each)
- Report: true positive rate, false positive rate on tamper detection
- Have this number memorized before the demo — judges ask.

---

## 7. Team Roles

| Role | Owns |
|---|---|
| OCR/MRZ | Extraction + checksum + cross-field rules |
| CV | Photo tamper detection (ELA) |
| ML | Face embedding + similarity matching |
| Backend | FastAPI endpoint, SQLite blacklist |
| Frontend | Upload UI, flag display |
| Docs/Pitch | Dataset sourcing, demo script, slides |

Adjust based on your actual team size — on a 6-person SIH team, some of these merge.

---

## 8. Demo Script (keep it live, not slides)

1. Upload a clean passport → shows "Pass" with all checks green.
2. Upload a tampered passport (edited DOB) → shows exact flag: "MRZ checksum mismatch on line 2, expected X got Y."
3. Upload a document with a face matching a blacklist entry under a different name → shows match + confidence.
4. Close with false-positive rate number and deployment cost/offline capability note (SSB checkpoints have poor connectivity — mention on-device inference).