"""
PhilVerify — TF-IDF + Logistic Regression Baseline Classifier (Layer 1)
Seed dataset of 30 labeled PH news headlines (10 per class).
Replaced by fine-tuned XLM-RoBERTa in Phase 10.
"""
import os
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "models" / "tfidf_model.pkl"

# ── Seed dataset (30 samples — 10 per class) ──────────────────────────────────
# Labels: 0=Credible, 1=Unverified, 2=Fake
SEED_DATA = [
    # Credible (0)
    ("DOH reports 500 new COVID-19 cases as vaccination drive continues in Metro Manila", 0),
    ("Rappler: Supreme Court upholds Comelec ruling on disqualification case", 0),
    ("GMA News: PNP arrests 12 suspects in Bulacan drug bust", 0),
    ("Philippine Star: GDP growth slows to 5.3% in Q3 says BSP", 0),
    ("Inquirer: Senate passes revised anti-terrorism bill on third reading", 0),
    ("Manila Bulletin: Typhoon Carina leaves P2B damage in Isabela province", 0),
    ("ABS-CBN News: Marcos signs executive order on agricultural modernization", 0),
    ("DOF confirms revenue collection targets met for fiscal year 2025", 0),
    ("DSWD distributes relief packs to 10,000 families in Cotabato", 0),
    ("PhilStar: Meralco rate hike of P0.18 per kilowatt-hour approved by ERC", 0),

    # Unverified (1)
    ("SHOCKING: Politician caught taking selfie during Senate hearing", 1),
    ("VIRAL: Celebrity spotted at secret meeting with government official", 1),
    ("BREAKING: 'Anonymous source' says president planning cabinet reshuffle", 1),
    ("Rumor has it: New tax policy to affect OFW remittances starting 2026", 1),
    ("CLAIM: Government hiding true COVID-19 death count from public", 1),
    ("Unconfirmed: Military says there are 500 rebels still in Mindanao", 1),
    ("REPORT: Certain barangay officials accepting bribes according to residents", 1),
    ("Alleged: Shipment of smuggled goods found in Manila port last week", 1),
    ("CLAIM: New mandatory vaccine policy for all government employees", 1),
    ("Source says: Manila Water to increase rates by 20% next month", 1),

    # Fake (2)
    ("GRABE! Namatay daw ang tatlong tao sa bagong sakit na kumakalat sa Pilipinas!", 2),
    ("TOTOO BA? Marcos nagsabi na libreng kuryente na simula bukas!", 2),
    ("SHOCKING TRUTH: Bill Gates microchip found in COVID vaccine in Cebu!", 2),
    ("WATCH: Senator caught stealing money in Senate vault - full video", 2),
    ("CONFIRMED: Philippines to become 51st state of the United States in 2026!", 2),
    ("KATOTOHANAN: DOH secretly poisoning water supply to control population", 2),
    ("EXPOSED: Duterte has secret family in Davao that government is hiding", 2),
    ("100% TOTOO: Garlic cures COVID-19, doctors don't want you to know this!", 2),
    ("GALING NG PILIPINAS: Filipino scientist discovers cure for cancer, suppressed by big pharma", 2),
    ("BREAKING: Entire Luzon to experience 3-day total blackout next week, says NGCP", 2),
]


@dataclass
class Layer1Result:
    verdict: str         # "Credible" | "Unverified" | "Fake"
    confidence: float    # 0.0 – 100.0
    triggered_features: list[str] = field(default_factory=list)


class TFIDFClassifier:
    """
    TF-IDF + Logistic Regression baseline.
    Train() fits on the seed dataset and saves to disk.
    Predict() loads persisted model first call.
    """

    _LABELS = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}

    def __init__(self):
        self._vectorizer = None
        self._clf = None

    def train(self) -> None:
        """Fit on seed data. Skips training if persisted model exists."""
        if MODEL_PATH.exists():
            self._load()
            return

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        texts, labels = zip(*SEED_DATA)
        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=1000,
            sublinear_tf=True,
        )
        X = self._vectorizer.fit_transform(texts)
        self._clf = LogisticRegression(max_iter=500, C=1.0, random_state=42)
        self._clf.fit(X, labels)

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"vectorizer": self._vectorizer, "clf": self._clf}, f)
        logger.info("TF-IDF model trained and saved to %s", MODEL_PATH)

    def _load(self) -> None:
        with open(MODEL_PATH, "rb") as f:
            data = pickle.load(f)
        self._vectorizer = data["vectorizer"]
        self._clf = data["clf"]
        logger.info("TF-IDF model loaded from %s", MODEL_PATH)

    def predict(self, text: str) -> Layer1Result:
        if self._vectorizer is None:
            self.train()

        X = self._vectorizer.transform([text])
        pred_label = int(self._clf.predict(X)[0])
        proba = self._clf.predict_proba(X)[0]
        confidence = round(float(max(proba)) * 100, 1)
        verdict = self._LABELS[pred_label]

        # Extract top TF-IDF features as human-readable triggers
        feature_names = self._vectorizer.get_feature_names_out()
        tfidf_scores = X.toarray()[0]
        top_indices = tfidf_scores.argsort()[-5:][::-1]
        triggered = [feature_names[i] for i in top_indices if tfidf_scores[i] > 0]

        return Layer1Result(
            verdict=verdict,
            confidence=confidence,
            triggered_features=triggered,
        )
