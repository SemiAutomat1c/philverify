"""
PhilVerify — Whisper ASR Module
Transcribes video/audio files using OpenAI Whisper.
Also provides combined ASR + frame OCR for full video text extraction.
Recommended model: large-v3 (best Filipino speech accuracy).
"""
import asyncio
import logging
import tempfile
import os

logger = logging.getLogger(__name__)


async def transcribe_video(media_bytes: bytes, filename: str = "upload") -> str:
    """
    Transcribe audio/video bytes using Whisper.
    Saves bytes to a temp file (Whisper requires file path, not bytes).
    Returns the transcript string.
    """
    try:
        import whisper
        from config import get_settings
        settings = get_settings()

        model_size = settings.whisper_model_size
        logger.info("Loading Whisper model: %s", model_size)

        model = whisper.load_model(model_size)

        # Whisper needs a file path — write bytes to temp file
        suffix = os.path.splitext(filename)[-1] or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(media_bytes)
            tmp_path = tmp.name

        try:
            result = model.transcribe(tmp_path, language=None)  # Auto-detect language
            transcript = result.get("text", "").strip()
            logger.info("Whisper transcribed %d chars (lang=%s)", len(transcript), result.get("language"))
            return transcript
        finally:
            os.unlink(tmp_path)  # Clean up temp file

    except ImportError:
        logger.warning("openai-whisper not installed — ASR unavailable")
        return ""
    except Exception as e:
        logger.error("Whisper transcription failed: %s", e)
        return ""


async def transcribe_and_ocr_video(media_bytes: bytes, filename: str = "upload") -> str:
    """
    Full video text extraction: runs Whisper ASR and frame OCR in parallel,
    then merges results based on what was found.

    Cases handled:
      - Audio only (no on-screen text)  → returns speech transcript alone
      - On-screen text only (silent)    → returns OCR text alone
      - Both                            → returns labelled combination
      - Neither                         → returns empty string (caller raises 422)
    """
    from inputs.video_ocr import extract_text_from_video_frames

    # Run Whisper ASR and frame OCR concurrently
    speech_text, ocr_text = await asyncio.gather(
        transcribe_video(media_bytes, filename=filename),
        extract_text_from_video_frames(media_bytes, filename=filename),
    )

    speech_text = (speech_text or "").strip()
    ocr_text = (ocr_text or "").strip()

    has_speech = len(speech_text) >= 10
    has_ocr = len(ocr_text) >= 10

    if has_speech and has_ocr:
        logger.info("Video has both speech (%d chars) and on-screen text (%d chars) — combining", len(speech_text), len(ocr_text))
        return f"[SPEECH]\n{speech_text}\n\n[ON-SCREEN TEXT]\n{ocr_text}"

    if has_speech:
        logger.info("Video has speech only (%d chars)", len(speech_text))
        return speech_text

    if has_ocr:
        logger.info("Video has on-screen text only (%d chars)", len(ocr_text))
        return ocr_text

    logger.warning("Video yielded no usable text from either ASR or frame OCR")
    return ""
