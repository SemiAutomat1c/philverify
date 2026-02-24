"""
PhilVerify — OCR Module (Tesseract)
Extracts text from images using pytesseract.
Falls back gracefully if Tesseract not installed.
"""
import io
import logging

logger = logging.getLogger(__name__)

# Supported languages: Filipino (fil) + English (eng)
_TESSERACT_LANG = "fil+eng"


async def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Run Tesseract OCR on image bytes. Returns extracted text string.
    """
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        text = pytesseract.image_to_string(image, lang=_TESSERACT_LANG)
        text = text.strip()
        logger.info("OCR extracted %d chars from image", len(text))
        return text
    except ImportError:
        logger.warning("pytesseract / Pillow not installed — OCR unavailable")
        return ""
    except Exception as e:
        logger.error("OCR failed: %s", e)
        return ""
