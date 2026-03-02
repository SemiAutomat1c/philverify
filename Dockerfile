# ── PhilVerify API — Dockerfile (Cloud Run + Hugging Face Spaces) ─────────────
# Build:  docker build -t philverify-api .
# Run:    docker run -p 7860:7860 --env-file .env philverify-api

FROM python:3.12-slim

# ── System dependencies ───────────────────────────────────────────────────────
# tesseract: OCR for image verification
# ffmpeg:    audio decoding for Whisper (video/audio input)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fil \
    tesseract-ocr-eng \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
# Upgrade pip + add setuptools (required by openai-whisper's setup.py on 3.12-slim)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Download spaCy English model (small, ~12 MB)
RUN python -m spacy download en_core_web_sm || true

# Download NLTK data used by the NLP pipeline
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True); nltk.download('punkt_tab', quiet=True)" || true

# ── Application code ──────────────────────────────────────────────────────────
COPY . .

# Remove local secrets — Cloud Run uses its own service account (ADC)
# The serviceAccountKey.json is NOT needed inside the container.
RUN rm -f serviceAccountKey.json .env

# Pre-download Whisper base model so cold starts are faster
RUN python -c "import whisper; whisper.load_model('base')" || true

# Pre-download HuggingFace transformer models used by the NLP pipeline so that
# cold starts don't hit the network — these would otherwise be fetched on the
# first /verify request and cause a Firebase Hosting 502 timeout (~1.2 GB total).
RUN python -c "\
from transformers import pipeline; \
print('Downloading twitter-roberta-base-sentiment...'); \
pipeline('text-classification', model='cardiffnlp/twitter-roberta-base-sentiment-latest'); \
print('Downloading emotion-english-distilroberta...'); \
pipeline('text-classification', model='j-hartmann/emotion-english-distilroberta-base'); \
print('Downloading distilbart-cnn-6-6 (claim extractor)...'); \
pipeline('summarization', model='sshleifer/distilbart-cnn-6-6'); \
print('All HuggingFace models cached.'); \
" || true

# ── Runtime ───────────────────────────────────────────────────────────────────
# HF Spaces uses port 7860 by default. Cloud Run overrides PORT via env var.
ENV PORT=7860
ENV APP_ENV=production
ENV DEBUG=false

EXPOSE 7860

# Use exec form so signals (SIGTERM) reach uvicorn directly
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 75"]
