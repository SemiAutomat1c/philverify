"""
PhilVerify — Whisper ASR Module
Transcribes video/audio files using OpenAI Whisper.
Recommended model: large-v3 (best Filipino speech accuracy).
"""
import io
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
