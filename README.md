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

---

## ✨ Features

- **🎤 Multimodal Detection** — Verify raw text, news URLs, images (Tesseract OCR), and video/audio (Whisper ASR)
- **🇵🇭 Language-Aware** — Seamlessly handles Tagalog, English, and Taglish content
- **🧠 Advanced NLP Pipeline** — Real-time entity recognition, sentiment/emotion analysis, and clickbait detection
- **⚖️ Two-Layer Scoring** — Combines ML classification (TF-IDF/RoBERTa) with NewsAPI evidence retrieval
- **🛡️ PH-Domain Verification** — Integrated database of Philippine news domain credibility tiers

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.12+**
2. **Tesseract OCR** (`brew install tesseract`)
3. **Node.js** (for frontend development)

### Installation

```bash
# Clone the repository
git clone https://github.com/SemiAutomat1c/philverify.git
cd philverify

# Set up Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up Frontend
cd frontend
npm install
```

### Run

```bash
# Backend (from project root)
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Core Backend** | Python 3.12, FastAPI, Pydantic v2 |
| **NLP Engine** | spaCy, HuggingFace Transformers, langdetect |
| **ML Classification** | scikit-learn (TF-IDF + LogReg), XLM-RoBERTa |
| **OCR / ASR** | Tesseract (PH+EN support), OpenAI Whisper |
| **Frontend** | React, TailwindCSS, Chart.js, Vite |

---

## 📁 Project Structure

```
PhilVerify/
├── main.py                  # FastAPI app entry point
├── config.py                # Settings (pydantic-settings)
├── requirements.txt
├── .env.example
├── domain_credibility.json  # PH domain tier database
│
├── api/
│   ├── schemas.py           # Pydantic request/response models
│   └── routes/
│       ├── verify.py        # POST /verify/text|url|image|video
│       ├── history.py       # GET /history
│       └── trends.py        # GET /trends
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
│   ├── ocr.py               # Tesseract OCR
│   └── asr.py               # Whisper ASR
│
└── tests/
    └── test_philverify.py   # 23 unit + integration tests
```

---

## 📅 Roadmap

- [x] Phase 1 — FastAPI backend skeleton
- [x] Phase 2 — NLP preprocessing pipeline
- [x] Phase 3 — TF-IDF baseline classifier
- [/] Phase 4 — NewsAPI evidence retrieval
- [ ] Phase 5 — Scoring engine refinement (stance detection)
- [ ] Phase 6 — React web dashboard
- [ ] Phase 7 — Chrome Extension (Manifest V3)
- [ ] Phase 8 — Fine-tune XLM-RoBERTa / TLUnified-RoBERTa

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
