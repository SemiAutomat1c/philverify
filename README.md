# PhilVerify 🇵🇭🔍

**Machine learning 2 final project**

**Multimodal fake news detection for Philippine social media.**

PhilVerify combines ML-based text classification with evidence retrieval to detect misinformation in Tagalog, English, and Taglish content. It supports text, URL, image (OCR), and video (ASR) inputs.

---

## Features

- **4 Input Types** — raw text, news URL, image (Tesseract OCR), video/audio (Whisper ASR)
- **Language-Aware** — detects Tagalog / English / Taglish automatically
- **NLP Pipeline** — NER, sentiment, emotion, clickbait detection, claim extraction
- **Two-Layer Scoring**
  - Layer 1: TF-IDF + Logistic Regression classifier (→ fine-tuned XLM-RoBERTa)
  - Layer 2: NewsAPI evidence retrieval + cosine similarity + stance detection
- **Final Score** = `(ML × 0.40) + (Evidence × 0.60)` → Credible / Unverified / Likely Fake
- **Philippine Domain Credibility DB** — 4-tier system (Rappler Tier 1 → known fake sites Tier 4)

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, Python 3.12, Pydantic v2 |
| NLP | spaCy, HuggingFace Transformers, langdetect |
| ML Classifier | scikit-learn (TF-IDF + LogReg → XLM-RoBERTa) |
| OCR | Tesseract (`fil+eng`) |
| ASR | OpenAI Whisper |
| Evidence | NewsAPI, sentence-transformers |
| Frontend *(planned)* | React, TailwindCSS, Chart.js |
| Extension *(planned)* | Chrome Manifest V3 |

---

## Project Structure

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

## Getting Started

### 1. Clone & set up environment

```bash
git clone https://github.com/SemiAutomat1c/philverify.git
cd philverify
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and add your NEWS_API_KEY (optional but recommended)
```

### 3. Run the API

```bash
uvicorn main:app --reload --port 8000
```

### 4. Explore the docs

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/verify/text` | Verify raw text |
| `POST` | `/verify/url` | Verify a news URL |
| `POST` | `/verify/image` | Verify an image (OCR) |
| `POST` | `/verify/video` | Verify audio/video (Whisper ASR) |
| `GET` | `/history` | Verification history (paginated) |
| `GET` | `/trends` | Trending fake-news entities & topics |

### Example request

```bash
curl -X POST http://localhost:8000/verify/text \
  -H "Content-Type: application/json" \
  -d '{"text": "GRABE! Namatay daw ang tatlong tao sa bagong sakit na kumakalat sa Pilipinas!"}'
```

### Example response

```json
{
  "verdict": "Likely Fake",
  "confidence": 82.4,
  "final_score": 34.2,
  "layer1": { "verdict": "Likely Fake", "confidence": 82.4, "triggered_features": ["namatay", "sakit", "kumakalat"] },
  "layer2": { "verdict": "Unverified", "evidence_score": 50.0, "sources": [] },
  "entities": { "persons": [], "organizations": [], "locations": ["Pilipinas"], "dates": [] },
  "sentiment": "high negative",
  "emotion": "fear",
  "language": "Tagalog"
}
```

---

## Running Tests

```bash
pytest tests/ -v
# 23 passed in ~1s
```

---

## Roadmap

- [x] Phase 1 — FastAPI backend skeleton
- [x] Phase 2 — NLP preprocessing pipeline
- [x] Phase 3 — TF-IDF baseline classifier
- [ ] Phase 4 — NewsAPI evidence retrieval
- [ ] Phase 5 — Scoring engine refinement (stance detection)
- [ ] Phase 6 — React web dashboard
- [ ] Phase 7 — Chrome Extension (Manifest V3)
- [ ] Phase 8 — Fine-tune XLM-RoBERTa / TLUnified-RoBERTa

---

## License

MIT
