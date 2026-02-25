"""
PhilVerify — Domain Credibility Module (Phase 5)
Wraps domain_credibility.json to provide structured tier lookups
for evidence source URLs and news article domains.

Tiers:
  Tier 1 (CREDIBLE)       — Established PH news orgs (Rappler, Inquirer, GMA, etc.)
  Tier 2 (SATIRE_OPINION) — Satire, opinion blogs, entertainment
  Tier 3 (SUSPICIOUS)     — Unknown / newly registered / low authority
  Tier 4 (KNOWN_FAKE)     — Vera Files blacklisted fake news sites
"""
import json
import logging
import re
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from urllib.parse import urlparse
import functools

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "domain_credibility.json"

# Score adjustments per tier (applied in scoring engine)
TIER_SCORE_ADJUSTMENT: dict[int, float] = {
    1: +20.0,   # Established PH news — credibility boost
    2:  -5.0,   # Satire/opinion — mild penalty
    3: -10.0,   # Unknown — moderate penalty
    4: -35.0,   # Known fake — heavy penalty
}

TIER_LABELS: dict[int, str] = {
    1: "Credible",
    2: "Satire/Opinion",
    3: "Suspicious",
    4: "Known Fake",
}


class DomainTier(IntEnum):
    CREDIBLE = 1
    SATIRE_OPINION = 2
    SUSPICIOUS = 3
    KNOWN_FAKE = 4


@dataclass
class DomainResult:
    domain: str
    tier: DomainTier
    tier_label: str
    score_adjustment: float
    matched_entry: str | None = None   # Which entry in the JSON matched


@functools.lru_cache(maxsize=1)
def _load_db() -> dict:
    """Load and cache the domain_credibility.json file."""
    try:
        data = json.loads(_DB_PATH.read_text())
        total = sum(len(v.get("domains", [])) for v in data.values())
        logger.info("domain_credibility.json loaded — %d domains across %d tiers", total, len(data))
        return data
    except Exception as e:
        logger.error("Failed to load domain_credibility.json: %s", e)
        return {}


def extract_domain(url_or_domain: str) -> str:
    """
    Normalize a URL or raw domain string to a bare hostname.

    Examples:
        "https://www.rappler.com/news/..." → "rappler.com"
        "www.gmanetwork.com"              → "gmanetwork.com"
        "inquirer.net"                    → "inquirer.net"
    """
    if not url_or_domain:
        return ""
    raw = url_or_domain.strip().lower()
    # Add scheme if missing so urlparse works correctly
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    try:
        hostname = urlparse(raw).hostname or ""
        # Strip leading www.
        hostname = re.sub(r"^www\.", "", hostname)
        return hostname
    except Exception:
        # Last resort — strip www. manually
        return re.sub(r"^www\.", "", raw.split("/")[0])


def lookup_domain(url_or_domain: str) -> DomainResult:
    """
    Classify a domain/URL against the credibility tier database.

    Args:
        url_or_domain: Full URL or bare domain name.

    Returns:
        DomainResult — Tier 3 (Suspicious) by default for unknown domains.
    """
    domain = extract_domain(url_or_domain)
    if not domain:
        return _make_result("", DomainTier.SUSPICIOUS, None)

    db = _load_db()

    for tier_key, tier_data in db.items():
        tier_num = int(tier_key[-1])            # "tier1" → 1
        for entry in tier_data.get("domains", []):
            # Match exact domain or subdomain of listed domain
            if domain == entry or domain.endswith(f".{entry}"):
                return _make_result(domain, DomainTier(tier_num), entry)

    # Not found → Tier 3 (Suspicious/Unknown)
    logger.debug("Domain '%s' not in credibility DB — defaulting to Tier 3 (Suspicious)", domain)
    return _make_result(domain, DomainTier.SUSPICIOUS, None)


def _make_result(domain: str, tier: DomainTier, matched_entry: str | None) -> DomainResult:
    return DomainResult(
        domain=domain,
        tier=tier,
        tier_label=TIER_LABELS[tier.value],
        score_adjustment=TIER_SCORE_ADJUSTMENT[tier.value],
        matched_entry=matched_entry,
    )


def get_tier_score(url_or_domain: str) -> float:
    """
    Convenience: return just the score adjustment for a domain.
    Positive = credibility boost, negative = penalty.
    """
    return lookup_domain(url_or_domain).score_adjustment


def is_blacklisted(url_or_domain: str) -> bool:
    """Return True if the domain is a known fake news / blacklisted site."""
    return lookup_domain(url_or_domain).tier == DomainTier.KNOWN_FAKE


def describe_tier(tier: DomainTier) -> str:
    """Human-readable tier description for API responses."""
    db = _load_db()
    key = f"tier{tier.value}"
    return db.get(key, {}).get("description", TIER_LABELS[tier.value])
