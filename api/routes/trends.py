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

# Reads from the same in-memory store as history (Phase 7 → DB aggregation).
from api.routes.history import _HISTORY


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

    entity_counter: Counter = Counter()
    entity_type_map: dict[str, str] = {}
    entity_fake_counter: Counter = Counter()
    topic_counter: Counter = Counter()
    topic_verdict_map: dict[str, list[str]] = {}

    for entry in _HISTORY:
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

    return TrendsResponse(top_entities=top_entities, top_topics=top_topics)
