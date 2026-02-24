"""
PhilVerify — FastAPI Application Entry Point
Run: uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from api.routes.verify import router as verify_router
from api.routes.history import router as history_router
from api.routes.trends import router as trends_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, get_settings().log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("philverify")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up NLP models on startup so first request isn't slow."""
    logger.info("🚀 PhilVerify starting up...")
    try:
        # Lazy-import to avoid crashing if heavy deps not yet installed
        from nlp.language_detector import LanguageDetector
        from nlp.preprocessor import TextPreprocessor
        from ml.tfidf_classifier import TFIDFClassifier

        app.state.preprocessor = TextPreprocessor()
        app.state.language_detector = LanguageDetector()
        classifier = TFIDFClassifier()
        classifier.train()          # Trains on seed dataset if model not persisted
        app.state.classifier = classifier

        logger.info("✅ NLP models ready")
    except ImportError as e:
        logger.warning("⚠️  Some NLP modules not installed yet: %s — stubs will be used", e)

    yield  # ── App is running ──

    logger.info("👋 PhilVerify shutting down")


# ── App ───────────────────────────────────────────────────────────────────────

settings = get_settings()

app = FastAPI(
    title="PhilVerify API",
    description=(
        "Multimodal fake news detection for Philippine social media. "
        "Supports text, URL, image (OCR), and video (Whisper ASR) inputs."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Error Handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(verify_router)
app.include_router(history_router)
app.include_router(trends_router)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "PhilVerify",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "env": settings.app_env}


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
