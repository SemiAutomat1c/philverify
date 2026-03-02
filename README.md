---
title: PhilVerify API
emoji: 🔍
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

<p align="center">
  <img src="frontend/public/logo.svg" alt="PhilVerify Logo" width="150">
</p>
<p align="center">
  <em>Multimodal fake news detection for Philippine social media.</em>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Machine_Learning_2-Final_Project-blue?style=flat-square" alt="Project Status">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License">
</p>
<p align="center">
  <a href="https://philverify.web.app"><strong>🌐 Live Demo</strong></a> &nbsp;•&nbsp;
  <a href="https://semiautomat1c-philverify-api.hf.space/docs"><strong>📖 API Docs</strong></a>
</p>

---

## ✨ Features

- **🎤 Multimodal Detection** — Verify raw text, news URLs, images, and video/audio
- **🖼️ Image OCR** — Extract and analyze text from screenshots and images (Tesseract fil+eng)
- **🎬 Video Frame OCR** — Extract on-screen text from video frames alongside Whisper speech transcription
- **🔊 Speech Transcription** — Transcribe audio/video content using OpenAI Whisper
- **🇵🇭 Language-Aware** — Seamlessly handles Tagalog, English, and Taglish content
- **🧠 Advanced NLP Pipeline** — Real-time entity recognition, sentiment/emotion analysis, and clickbait detection
- **⚖️ Two-Layer Scoring** — Combines ML classification (TF-IDF) with NewsAPI evidence retrieval
- **🛡️ PH-Domain Verification** — Integrated database of Philippine news domain credibility tiers

---

## 🚀 Deployment

| Service | Platform | URL |
|---------|----------|-----|
| **Frontend** | Firebase Hosting | https://philverify.web.app |
| **Backend API** | Hugging Face Spaces (Docker) | https://semiautomat1c-philverify-api.hf.space |
| **API Docs** | Swagger UI (auto-generated) | https://semiautomat1c-philverify-api.hf.space/docs |

---

## 🖥️ Local Development

### Prerequisites

1. **Python 3.12+**
2. **Tesseract OCR** — `brew install tesseract tesseract-lang`
3. **ffmpeg** — `brew install ffmpeg` (required for video frame extraction)
4. **Node.js 18+** (for frontend)

### Installation

```bash
# Clone the repository
git clone https://github.com/SemiAutomat1c/philverify.git
cd philverify

# Set up backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up frontend
cd frontend
npm install
```

### Run

```bash
# Backend (from project root, with venv active)
uvicorn main:app --reload --port 8000

# Frontend (in a separate terminal)
cd frontend
npm run dev
```

The frontend dev server proxies `/api` requests to `http://localhost:8000` automatically.

### Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```
NEWS_API_KEY=your_newsapi_key
FIREBASE_PROJECT_ID=your_project_id
```

For frontend production builds, set `VITE_API_BASE_URL` in `frontend/.env.production`:
```
VITE_API_BASE_URL=https://your-hf-space.hf.space/api
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Core Backend** | Python 3.12, FastAPI, Pydantic v2 |
| **NLP Engine** | spaCy, HuggingFace Transformers, langdetect |
| **ML Classification** | scikit-learn (TF-IDF + Logistic Regression) |
| **OCR** | Tesseract (fil+eng), pytesseract, Pillow |
| **ASR** | OpenAI Whisper (base model) |
| **Video Processing** | ffmpeg (frame extraction), asyncio parallel pipeline |
| **Frontend** | React 18, TailwindCSS, Chart.js, Vite 7 |
| **Backend Hosting** | Hugging Face Spaces (Docker SDK, port 7860) |
| **Frontend Hosting** | Firebase Hosting |

---

## 📁 Project Structure

```
PhilVerify/
├── main.py                  # FastAPI app entry point + health endpoints
├── config.py                # Settings (pydantic-settings)
├── requirements.txt
├── Dockerfile               # Docker image for HF Spaces (port 7860)
├── domain_credibility.json  # PH news domain credibility tier database
│
├── api/
│   ├── schemas.py           # Pydantic request/response models
│   └── routes/
│       ├── verify.py        # POST /api/verify — handles text/url/image/video
│       ├── history.py       # GET /api/history
│       └── trends.py        # GET /api/trends
│
├── nlp/                     # NLP preprocessing pipeline
│   ├── preprocessor.py      # Clean, tokenize, remove stopwords (EN+TL)
│   ├── language_detector.py # Tagalog / English / Taglish detection
│   ├── ner.py               # Named entity recognition + PH entity hints
│   ├── sentiment.py         # Sentiment + emotion analysis
│   ├── clickbait.py         # Clickbait pattern detection
│   └── claim_extractor.py   # Extract falsifiable claim for evidence search
│
├── ml/
│   └── tfidf_classifier.py  # Layer 1 — TF-IDF baseline classifier
│
├── evidence/
│   └── news_fetcher.py      # Layer 2 — NewsAPI + cosine similarity
│
├── scoring/
│   └── engine.py            # Orchestrates full pipeline + final score
│
├── inputs/
│   ├── url_scraper.py       # BeautifulSoup article extractor
│   ├── ocr.py               # Tesseract OCR for images
│   ├── asr.py               # Whisper ASR + combined video transcription
│   └── video_ocr.py         # ffmpeg frame extraction + Tesseract OCR for video
│
├── frontend/                # React + Vite frontend
│   ├── src/
│   │   ├── pages/
│   │   │   └── VerifyPage.jsx   # Main fact-check UI (tabs, results, chips)
│   │   └── api.js               # API client (supports VITE_API_BASE_URL)
│   └── .env.production          # Production API base URL
│
└── tests/
    └── test_philverify.py   # Unit + integration tests
```

---

## 📅 Roadmap

- [x] Phase 1 — FastAPI backend skeleton
- [x] Phase 2 — NLP preprocessing pipeline
- [x] Phase 3 — TF-IDF baseline classifier
- [x] Phase 4 — NewsAPI evidence retrieval
- [x] Phase 5 — React web dashboard with multimodal input
- [x] Phase 6 — Deploy to Hugging Face Spaces (backend) + Firebase (frontend)
- [x] Phase 7 — Video frame OCR (ffmpeg + Tesseract alongside Whisper ASR)
- [ ] Phase 8 — Scoring engine refinement (stance detection)
- [ ] Phase 9 — Chrome Extension (Manifest V3)
- [ ] Phase 10 — Fine-tune XLM-RoBERTa / TLUnified-RoBERTa

---

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

---

<p align="center">
  <strong>⚠️ Disclaimer</strong><br>
  <em>This tool is meant for research and educational purposes. Use responsibly and ethically when verifying information on social media.</em>
</p>

## 📝 License

MIT
