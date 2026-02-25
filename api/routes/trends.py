"""
PhilVerify — Trends Route
GET /trends — Aggregates entities and topics from fake-news verifications.
"""
import logging
from collections import Counter
from fastapi import APIRouter, Query
from api.schemas import TrendsResponse, TrendingEntity, TrendingTopic, Verdict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trends", tags=["Trends"])


def _load_all_history() -> list[dict]:
    """
    Return all history records from the best available source:
      1. Firestore  2. Local JSON file  3. In-memory list (fallback)
    """
    # Tier 1: Firestore
    try:
        from firebase_client import get_all_verifications_sync
        records = get_all_verifications_sync()
        if records:
            return records
    except Exception:
        pass

    # Tier 2: Local JSON file (persists across restarts)
    try:
        from api.routes.history import _load_history_file
        records = _load_history_file()
        if records:
            return records
    except Exception:
        pass

    # Tier 3: In-memory (empty after restart, but keeps current session data)
    from api.routes.history import _HISTORY
    return list(_HISTORY)


@router.get(
    "",
    response_model=TrendsResponse,
    summary="Get trending entities & topics",
    description="Aggregates NER entities and topics from recent verifications. Useful for identifying fake-news patterns.",
)
async def get_trends(
    days: int = Query(7, ge=1, le=90, description="Lookback window in days"),
    limit: int = Query(10, ge=1, le=50, description="Max results per category"),
) -> TrendsResponse:
    logger.info("GET /trends | days=%d", days)

    all_history = _load_all_history()

    entity_counter: Counter = Counter()
    entity_type_map: dict[str, str] = {}
    entity_fake_counter: Counter = Counter()
    topic_counter: Counter = Counter()
    topic_verdict_map: dict[str, list[str]] = {}

    for entry in all_history:
        is_fake = entry.get("verdict") in (Verdict.LIKELY_FAKE.value, Verdict.UNVERIFIED.value)
        entities = entry.get("entities", {})

        for person in entities.get("persons", []):
            entity_counter[person] += 1
            entity_type_map[person] = "person"
            if is_fake:
                entity_fake_counter[person] += 1

        for org in entities.get("organizations", []):
            entity_counter[org] += 1
            entity_type_map[org] = "org"
            if is_fake:
                entity_fake_counter[org] += 1

        for loc in entities.get("locations", []):
            entity_counter[loc] += 1
            entity_type_map[loc] = "location"
            if is_fake:
                entity_fake_counter[loc] += 1

        claim = entry.get("claim_used", "")
        if claim:
            topic_counter[claim[:60]] += 1
            topic_verdict_map.setdefault(claim[:60], []).append(entry.get("verdict", "Unverified"))

    top_entities = [
        TrendingEntity(
            entity=entity,
            entity_type=entity_type_map.get(entity, "unknown"),
            count=count,
            fake_count=entity_fake_counter.get(entity, 0),
            fake_ratio=round(entity_fake_counter.get(entity, 0) / count, 2),
        )
        for entity, count in entity_counter.most_common(limit)
    ]

    top_topics = [
        TrendingTopic(
            topic=topic,
            count=count,
            dominant_verdict=Verdict(
                Counter(topic_verdict_map.get(topic, ["Unverified"])).most_common(1)[0][0]
            ),
        )
        for topic, count in topic_counter.most_common(limit)
    ]

    # ── Verdict distribution totals ───────────────────────────────────────────────
    verdict_dist: dict[str, int] = {"Credible": 0, "Unverified": 0, "Likely Fake": 0}
    day_map: dict[str, dict[str, int]] = {}   # date → {Credible, Unverified, Likely Fake}

    for entry in all_history:
        v = entry.get("verdict", "Unverified")
        if v in verdict_dist:
            verdict_dist[v] += 1

        ts = entry.get("timestamp", "")
        date_key = ts[:10] if ts else ""   # YYYY-MM-DD prefix
        if date_key:
            bucket = day_map.setdefault(date_key, {"Credible": 0, "Unverified": 0, "Likely Fake": 0})
            if v in bucket:
                bucket[v] += 1

    from api.schemas import VerdictDayPoint
    verdict_by_day = [
        VerdictDayPoint(
            date=d,
            credible=day_map[d]["Credible"],
            unverified=day_map[d]["Unverified"],
            fake=day_map[d]["Likely Fake"],
        )
        for d in sorted(day_map.keys())
    ]

    return TrendsResponse(
        top_entities=top_entities,
        top_topics=top_topics,
        verdict_distribution=verdict_dist,
        verdict_by_day=verdict_by_day,
    )

