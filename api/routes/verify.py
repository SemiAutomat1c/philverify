"""
PhilVerify — Verify Routes
POST /verify/text | /verify/url | /verify/image | /verify/video
All routes funnel through run_verification() in the scoring engine.
"""
import time
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse

from api.schemas import (
    TextVerifyRequest,
    URLVerifyRequest,
    VerificationResponse,
    ErrorResponse,
)
from scoring.engine import run_verification
from inputs.url_scraper import scrape_url
from inputs.ocr import extract_text_from_image
from inputs.asr import transcribe_video

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/verify", tags=["Verification"])

# ── OG meta fallback for bot-protected / social URLs ──────────────────────────
async def _fetch_og_text(url: str) -> str:
    """
    Fetches OG/meta title + description from a URL using a plain HTTP GET.
    Used as a last-resort fallback when the full scraper returns no content
    (e.g. Facebook share links, photo URLs that block the scraper).
    Returns a concatenated title + description string, or "" on failure.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                return ""
            head_end = resp.text.find("</head>")
            head_html = resp.text[:head_end + 7] if head_end != -1 else resp.text[:8000]
            soup = BeautifulSoup(head_html, "lxml")

            def _m(prop=None, name=None):
                el = (soup.find("meta", property=prop) if prop
                      else soup.find("meta", attrs={"name": name}))
                return (el.get("content") or "").strip() if el else ""

            title = (_m(prop="og:title") or _m(name="twitter:title")
                     or (soup.title.get_text(strip=True) if soup.title else ""))
            description = (_m(prop="og:description") or _m(name="twitter:description")
                           or _m(name="description"))
            parts = [p for p in [title, description] if p]
            return " ".join(parts)
    except Exception as exc:
        logger.warning("OG meta fallback failed for %s: %s", url, exc)
        return ""


# ── Text ──────────────────────────────────────────────────────────────────────

@router.post(
    "/text",
    response_model=VerificationResponse,
    summary="Verify raw text",
    description="Accepts plain text (Tagalog, English, or Taglish) and runs the full verification pipeline.",
)
async def verify_text(body: TextVerifyRequest) -> VerificationResponse:
    start = time.perf_counter()
    logger.info("verify/text called | chars=%d", len(body.text))
    try:
        result = await run_verification(body.text, input_type="text")
        result.processing_time_ms = round((time.perf_counter() - start) * 1000, 1)
        result.extracted_text = body.text
        return result
    except Exception as exc:
        logger.exception("verify/text error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Verification failed: {exc}") from exc


# ── URL ───────────────────────────────────────────────────────────────────────

@router.post(
    "/url",
    response_model=VerificationResponse,
    summary="Verify a URL",
    description="Scrapes the article text from the given URL, then runs the full verification pipeline.",
)
async def verify_url(body: URLVerifyRequest) -> VerificationResponse:
    start = time.perf_counter()
    url_str = str(body.url)
    logger.info("verify/url called | url=%s", url_str)
    try:
        text, domain = await scrape_url(url_str)
        if not text or len(text.strip()) < 20:
            logger.info("scrape_url returned no content for %s — trying OG meta fallback", url_str)
            text = await _fetch_og_text(url_str)
        if not text or len(text.strip()) < 20:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not extract meaningful text from the URL. The page may be paywalled, private, or bot-protected. Try copying the post text and using the Text tab instead.",
            )
        result = await run_verification(text, input_type="url", source_domain=domain)
        result.processing_time_ms = round((time.perf_counter() - start) * 1000, 1)
        result.extracted_text = text.strip()
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        # Expected user-facing errors (e.g. robots.txt block, bad URL)
        logger.warning("verify/url rejected: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("verify/url error: %s", exc)
        raise HTTPException(status_code=500, detail=f"URL verification failed: {exc}") from exc


# ── Image ─────────────────────────────────────────────────────────────────────

@router.post(
    "/image",
    response_model=VerificationResponse,
    summary="Verify an image (OCR)",
    description="Accepts an uploaded image file. Runs Tesseract OCR to extract text, then verifies.",
)
async def verify_image(file: UploadFile = File(...)) -> VerificationResponse:
    start = time.perf_counter()
    logger.info("verify/image called | filename=%s | size=%s", file.filename, file.size)

    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type: {file.content_type}. Accepted: jpeg, png, webp, gif, bmp",
        )
    try:
        image_bytes = await file.read()
        text = await extract_text_from_image(image_bytes)
        if not text or len(text.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No readable text found in the image.",
            )
        result = await run_verification(text, input_type="image")
        result.processing_time_ms = round((time.perf_counter() - start) * 1000, 1)
        result.extracted_text = text.strip()
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("verify/image error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Image verification failed: {exc}") from exc


# ── Video ─────────────────────────────────────────────────────────────────────

@router.post(
    "/video",
    response_model=VerificationResponse,
    summary="Verify a video/audio (Whisper ASR)",
    description="Accepts a video or audio file. Runs Whisper ASR to transcribe, then verifies the transcript.",
)
async def verify_video(file: UploadFile = File(...)) -> VerificationResponse:
    start = time.perf_counter()
    logger.info("verify/video called | filename=%s", file.filename)

    allowed_types = {
        "video/mp4", "video/webm", "video/quicktime",
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type: {file.content_type}",
        )
    try:
        media_bytes = await file.read()
        text = await transcribe_video(media_bytes, filename=file.filename or "upload")
        if not text or len(text.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not transcribe meaningful speech from the media file.",
            )
        result = await run_verification(text, input_type="video")
        result.processing_time_ms = round((time.perf_counter() - start) * 1000, 1)
        result.extracted_text = text.strip()
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("verify/video error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Video verification failed: {exc}") from exc
