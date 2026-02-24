"""
PhilVerify — Named Entity Recognition
Extracts persons, organizations, locations, and dates from text.
Uses spaCy en_core_web_sm with graceful fallback if model not installed.
"""
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Philippine-specific named entity hints
_PH_PERSONS = {
    "marcos", "duterte", "aquino", "robredo", "lacson", "pingping",
    "bongbong", "sara", "panelo", "roque", "calida", "ano", "teodoro",
}
_PH_ORGS = {
    "doh", "deped", "dilg", "dfa", "dof", "dswd", "ched", "nbi", "pnp",
    "afp", "comelec", "sandiganbayan", "ombudsman", "pcso", "pagcor",
    "senate", "congress", "supreme court", "malacanang",
}
_PH_LOCATIONS = {
    "manila", "quezon city", "makati", "pasig", "taguig", "cebu",
    "davao", "mindanao", "luzon", "visayas", "palawan", "boracay",
    "batangas", "laguna", "cavite", "rizal", "bulacan", "pampanga",
    "metro manila", "ncr", "philippines", "pilipinas",
}


@dataclass
class NERResult:
    persons: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    method: str = "spacy"

    def to_dict(self) -> dict:
        return {
            "persons": self.persons,
            "organizations": self.organizations,
            "locations": self.locations,
            "dates": self.dates,
        }


class EntityExtractor:
    """
    NER using spaCy (en_core_web_sm) + Philippine entity hint layer.
    Falls back to regex-based date extraction if spaCy not installed.
    """

    def __init__(self):
        self._nlp = None
        self._loaded = False

    def _load_model(self):
        if self._loaded:
            return
        try:
            import spacy
            self._nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy en_core_web_sm loaded")
        except Exception as e:
            logger.warning("spaCy not available (%s) — using hint-based NER", e)
            self._nlp = None
        self._loaded = True

    def _hint_based_extract(self, text: str) -> NERResult:
        """Fallback: match PH-specific entity hint lists + date regex."""
        lower = text.lower()
        result = NERResult(method="hints")

        result.persons = [p.title() for p in _PH_PERSONS if p in lower]
        result.organizations = [o.upper() for o in _PH_ORGS if o in lower]
        result.locations = [loc.title() for loc in _PH_LOCATIONS if loc in lower]

        # Date patterns: "February 2026", "Feb 24, 2026", "2026-02-24"
        date_patterns = [
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"(?:\s+\d{1,2})?,?\s+\d{4}\b",
            r"\b\d{4}-\d{2}-\d{2}\b",
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        ]
        for pattern in date_patterns:
            result.dates.extend(re.findall(pattern, text, re.IGNORECASE))

        return result

    def extract(self, text: str) -> NERResult:
        self._load_model()

        if self._nlp is None:
            return self._hint_based_extract(text)

        try:
            doc = self._nlp(text[:5000])  # spaCy has a token limit
            result = NERResult(method="spacy")

            for ent in doc.ents:
                ent_text = ent.text.strip()
                if ent.label_ == "PERSON":
                    result.persons.append(ent_text)
                elif ent.label_ in ("ORG", "NORP"):
                    result.organizations.append(ent_text)
                elif ent.label_ in ("GPE", "LOC"):
                    result.locations.append(ent_text)
                elif ent.label_ in ("DATE", "TIME"):
                    result.dates.append(ent_text)

            # Deduplicate while preserving order
            result.persons = list(dict.fromkeys(result.persons))
            result.organizations = list(dict.fromkeys(result.organizations))
            result.locations = list(dict.fromkeys(result.locations))
            result.dates = list(dict.fromkeys(result.dates))

            # Supplement with PH hints for entities spaCy may miss
            hint_result = self._hint_based_extract(text)
            for p in hint_result.persons:
                if p not in result.persons:
                    result.persons.append(p)
            for o in hint_result.organizations:
                if o not in result.organizations:
                    result.organizations.append(o)

            return result
        except Exception as e:
            logger.warning("spaCy extraction error: %s — falling back to hints", e)
            return self._hint_based_extract(text)
