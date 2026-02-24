"""
PhilVerify — History Route
GET /history — Returns past verification logs with pagination.
"""
import logging
from fastapi import APIRouter, Query
from api.schemas import HistoryResponse, HistoryEntry, Verdict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/history", tags=["History"])

# In-memory store for development. Will be replaced by DB queries in Phase 7.
_HISTORY: list[dict] = []


def record_verification(entry: dict) -> None:
    """Called by the scoring engine to persist each verification result."""
    _HISTORY.append(entry)


@router.get(
    "",
    response_model=HistoryResponse,
    summary="Get verification history",
    description="Returns past verifications ordered by most recent. Supports pagination.",
)
async def get_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    verdict_filter: Verdict | None = Query(None, alias="verdict", description="Filter by verdict"),
) -> HistoryResponse:
    logger.info("GET /history | page=%d limit=%d", page, limit)

    entries = list(reversed(_HISTORY))  # Most recent first
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
