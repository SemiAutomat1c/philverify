"""
PhilVerify — History Route
GET /history — Returns past verification logs with pagination.

Persistence tier order (best to worst):
  1. Local JSON file — data/history.json, survives server restarts
  2. In-memory list — last resort, resets on every restart
"""
import json
import logging
import threading
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from api.schemas import HistoryResponse, HistoryEntry, Verdict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/history", tags=["History"])

# ── Local JSON file store ─────────────────────────────────────────────────────
# Survives server restarts. Used when Firestore is unavailable (e.g. API disabled).
_HISTORY_FILE = Path(__file__).parent.parent.parent / "data" / "history.json"
_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
_file_lock = threading.Lock()  # Guard concurrent writes


def _load_history_file() -> list[dict]:
    """Read all records from the local JSON history file."""
    try:
        if _HISTORY_FILE.exists():
            return json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Could not read history file: %s", e)
    return []


def _append_history_file(entry: dict) -> None:
    """Atomically append one entry to the local JSON history file."""
    with _file_lock:
        records = _load_history_file()
        records.append(entry)
        try:
            _HISTORY_FILE.write_text(
                json.dumps(records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Could not write history file: %s", e)


# In-memory fallback (last resort — loses data on restart)
_HISTORY: list[dict] = []


def record_verification(entry: dict) -> None:
    """
    Called by the scoring engine after every verification.
    Writes to the local JSON file so history persists even without Firestore.
    Also keeps the in-memory list in sync for the current process lifetime.
    """
    _HISTORY.append(entry)
    _append_history_file(entry)


@router.get(
    "/{entry_id}",
    summary="Get single verification by ID",
    description="Returns the full raw record for a single verification, including layer scores, entities, sentiment.",
)
async def get_history_entry(entry_id: str) -> dict:
    logger.info("GET /history/%s", entry_id)

    # Tier 1: Local JSON file
    try:
        records = _load_history_file()
        for r in records:
            if r.get("id") == entry_id:
                return r
    except Exception:
        pass

    # Tier 3: In-memory
    for r in _HISTORY:
        if r.get("id") == entry_id:
            return r

    raise HTTPException(status_code=404, detail="Verification not found")


@router.get(
    "",
    response_model=HistoryResponse,
    summary="Get verification history",
    description="Returns past verifications ordered by most recent. Reads from local JSON file, falls back to in-memory store.",
)
async def get_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    verdict_filter: Verdict | None = Query(None, alias="verdict", description="Filter by verdict"),
) -> HistoryResponse:
    logger.info("GET /history | page=%d limit=%d", page, limit)

    # ── Tier 1: Local JSON file ───────────────────────────────────────────────
    # Load from file rather than in-memory list so data survives restarts.
    file_entries = list(reversed(_load_history_file()))
    if file_entries:
        if verdict_filter:
            file_entries = [e for e in file_entries if e.get("verdict") == verdict_filter.value]
        total = len(file_entries)
        start = (page - 1) * limit
        paginated = file_entries[start : start + limit]
        return HistoryResponse(
            total=total,
            entries=[
                HistoryEntry(
                    id=e["id"],
                    timestamp=e["timestamp"],
                    input_type=e.get("input_type", "text"),
                    text_preview=e.get("text_preview", "")[:120],
                    verdict=Verdict(e["verdict"]),
                    confidence=e["confidence"],
                    final_score=e["final_score"],
                )
                for e in paginated
            ],
        )

    # ── Tier 3: In-memory (last resort — resets on restart) ───────────────────
    entries = list(reversed(_HISTORY))
    if verdict_filter:
        entries = [e for e in entries if e.get("verdict") == verdict_filter.value]
    total = len(entries)
    start = (page - 1) * limit
    paginated = entries[start : start + limit]
    return HistoryResponse(
        total=total,
        entries=[
            HistoryEntry(
                id=e["id"],
                timestamp=e["timestamp"],
                input_type=e.get("input_type", "text"),
                text_preview=e.get("text_preview", "")[:120],
                verdict=Verdict(e["verdict"]),
                confidence=e["confidence"],
                final_score=e["final_score"],
            )
            for e in paginated
        ],
    )
