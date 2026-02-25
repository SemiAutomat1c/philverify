"""
PhilVerify — Firebase / Firestore Client
Initializes firebase-admin SDK and provides typed helpers for persistence.

Setup:
  1. Go to Firebase Console → Project Settings → Service Accounts
  2. Click "Generate new private key" → save as `serviceAccountKey.json`
     in the PhilVerify project root (already in .gitignore)
  3. Set FIREBASE_PROJECT_ID in .env

Collections:
  verifications/   — one doc per verification run
  trends/summary   — aggregated entity/topic counters
"""
import logging
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_SERVICEACCOUNT_PATH = Path(__file__).parent / "serviceAccountKey.json"
_db = None  # Firestore client singleton


def get_firestore():
    """Return the Firestore client, or None if Firebase is not configured."""
    global _db
    if _db is not None:
        return _db

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
            _db = firestore.client()
            return _db

        if _SERVICEACCOUNT_PATH.exists():
            # Service account key file available (local dev + CI)
            cred = credentials.Certificate(str(_SERVICEACCOUNT_PATH))
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized via service account key")
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("K_SERVICE"):
            # Cloud Run (K_SERVICE is always set) or explicit ADC path
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized via Application Default Credentials")
        else:
            logger.warning(
                "Firebase not configured — no serviceAccountKey.json and no "
                "GOOGLE_APPLICATION_CREDENTIALS env var. History will use in-memory store."
            )
            return None

        _db = firestore.client()
        return _db

    except ImportError:
        logger.warning("firebase-admin not installed — Firestore disabled")
        return None
    except Exception as e:
        logger.error("Firebase init error: %s — falling back to in-memory store", e)
        return None


async def save_verification(data: dict) -> bool:
    """
    Persist a verification result to Firestore.
    Returns True on success, False if Firebase is unavailable.
    """
    db = get_firestore()
    if db is None:
        return False
    try:
        db.collection("verifications").document(data["id"]).set(data)
        logger.debug("Verification %s saved to Firestore", data["id"])
        return True
    except Exception as e:
        logger.error("Firestore write error: %s", e)
        return False


async def get_verifications(
    limit: int = 20,
    offset: int = 0,
    verdict_filter: str | None = None,
) -> list[dict]:
    """Fetch verification history from Firestore ordered by timestamp desc."""
    db = get_firestore()
    if db is None:
        return []
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = (
            db.collection("verifications")
            .order_by("timestamp", direction="DESCENDING")
        )
        if verdict_filter:
            query = query.where(filter=FieldFilter("verdict", "==", verdict_filter))
        docs = query.limit(limit + offset).stream()
        results = [doc.to_dict() for doc in docs]
        return results[offset : offset + limit]
    except Exception as e:
        logger.error("Firestore read error: %s", e)
        return []


def get_all_verifications_sync() -> list[dict]:
    """Synchronously fetch ALL verification records from Firestore (used by trends aggregation)."""
    db = get_firestore()
    if db is None:
        return []
    try:
        docs = (
            db.collection("verifications")
            .order_by("timestamp", direction="DESCENDING")
            .limit(10_000)  # hard cap — more than enough for trends analysis
            .stream()
        )
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error("Firestore get_all_verifications_sync error: %s", e)
        return []


async def get_verification_count(verdict_filter: str | None = None) -> int:
    """Return total count of verifications (with optional verdict filter)."""
    db = get_firestore()
    if db is None:
        return 0
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = db.collection("verifications")
        if verdict_filter:
            query = query.where(filter=FieldFilter("verdict", "==", verdict_filter))
        # Use aggregation query (Firestore native count)
        result = query.count().get()
        return result[0][0].value
    except Exception as e:
        logger.error("Firestore count error: %s", e)
        return 0
