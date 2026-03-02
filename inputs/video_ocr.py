"""
PhilVerify — Video Frame OCR Module
Extracts on-screen text from video files by sampling frames with ffmpeg
and running Tesseract OCR on each frame.

Strategy:
  - Extract 1 frame every FRAME_INTERVAL seconds using ffmpeg (already in Docker)
  - Run existing Tesseract OCR on each frame
  - Deduplicate consecutive near-identical frames (static lower-thirds, etc.)
  - Return unique on-screen text joined by newlines
"""
import asyncio
import logging
import os
import subprocess
import tempfile
from difflib import SequenceMatcher

from inputs.ocr import extract_text_from_image

logger = logging.getLogger(__name__)

# Sample 1 frame every N seconds — good balance for news/social media clips
FRAME_INTERVAL = 3
# Similarity threshold — skip frame if >80% similar to previous (avoids repeating static text)
SIMILARITY_THRESHOLD = 0.80
# Minimum meaningful OCR text length per frame
MIN_FRAME_CHARS = 8


def _similarity(a: str, b: str) -> float:
    """Return similarity ratio between two strings (0.0 – 1.0)."""
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def _extract_frames_with_ffmpeg(video_path: str, output_dir: str) -> list[str]:
    """
    Use ffmpeg to extract 1 frame every FRAME_INTERVAL seconds as JPEG files.
    Returns list of frame file paths. Returns [] on failure.
    """
    pattern = os.path.join(output_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps=1/{FRAME_INTERVAL}",
        "-q:v", "2",          # high quality JPEG
        "-frames:v", "300",   # safety cap: max 300 frames (~15 min @ 3s interval)
        pattern,
        "-y",                 # overwrite
        "-loglevel", "error", # suppress noise
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            logger.warning("ffmpeg frame extraction failed: %s", result.stderr.decode())
            return []
        frames = sorted(f for f in os.listdir(output_dir) if f.endswith(".jpg"))
        logger.info("ffmpeg extracted %d frames from video", len(frames))
        return [os.path.join(output_dir, f) for f in frames]
    except FileNotFoundError:
        logger.warning("ffmpeg not found — video OCR unavailable")
        return []
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg frame extraction timed out")
        return []
    except Exception as e:
        logger.error("ffmpeg error: %s", e)
        return []


async def extract_text_from_video_frames(media_bytes: bytes, filename: str = "upload.mp4") -> str:
    """
    Extract on-screen text from a video by sampling frames with ffmpeg
    and running Tesseract OCR on each frame.

    Returns deduplicated on-screen text, or empty string if no text found
    or ffmpeg/tesseract unavailable.
    """
    suffix = os.path.splitext(filename)[-1] or ".mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write video bytes to temp file
        video_path = os.path.join(tmpdir, f"input{suffix}")
        with open(video_path, "wb") as f:
            f.write(media_bytes)

        frames_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frames_dir)

        # Extract frames (blocking — run in executor to avoid blocking event loop)
        loop = asyncio.get_event_loop()
        frame_paths = await loop.run_in_executor(
            None, _extract_frames_with_ffmpeg, video_path, frames_dir
        )

        if not frame_paths:
            logger.info("No frames extracted — skipping video OCR")
            return ""

        # Run OCR on each frame, deduplicate consecutive similar text
        unique_texts: list[str] = []
        last_text = ""

        for frame_path in frame_paths:
            with open(frame_path, "rb") as f:
                frame_bytes = f.read()

            text = await extract_text_from_image(frame_bytes)
            text = text.strip()

            if len(text) < MIN_FRAME_CHARS:
                continue  # mostly blank frame

            if last_text and _similarity(text, last_text) > SIMILARITY_THRESHOLD:
                continue  # too similar to previous — static overlay, skip

            unique_texts.append(text)
            last_text = text

        result = "\n".join(unique_texts).strip()
        logger.info("Video OCR: %d unique text segments, %d total chars", len(unique_texts), len(result))
        return result
