"""
PhilVerify — Bag of Words + Logistic Regression Classifier (Layer 1)

CountVectorizer (BoW) with LogisticRegression. Identical to TFIDFClassifier except
for the vectorizer — this isolates the BoW vs TF-IDF comparison in eval.py.
Supports optional WordNet lemmatization.
"""
import logging

from ml.naive_bayes_classifier import _lemmatize_tokens
from ml.tfidf_classifier import Layer1Result

logger = logging.getLogger(__name__)


class BoWClassifier:
    """
    BoW (CountVectorizer) + LogisticRegression classifier.

    Args:
        train_samples: list[Sample] from ml.dataset. If None, uses the full 100-sample dataset.
        lemmatize:     apply WordNet lemmatization before vectorization.
    """

    _LABELS = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}

    def __init__(self, train_samples=None, lemmatize: bool = False):
        from sklearn.feature_extraction.text import CountVectorizer
        from sklearn.linear_model import LogisticRegression

        self._lemmatize = lemmatize

        if train_samples is None:
            from ml.dataset import get_dataset
            train_samples = get_dataset()

        texts = [self._preprocess(s.text) for s in train_samples]
        labels = [s.label for s in train_samples]

        self._vectorizer = CountVectorizer(ngram_range=(1, 2), max_features=1000)
        X = self._vectorizer.fit_transform(texts)

        self._clf = LogisticRegression(max_iter=500, C=1.0, random_state=42)
        self._clf.fit(X, labels)
        logger.info(
            "BoWClassifier trained on %d samples (lemmatize=%s)",
            len(texts), lemmatize,
        )

    def _preprocess(self, text: str) -> str:
        text = text.lower()
        if self._lemmatize:
            return " ".join(_lemmatize_tokens(text.split()))
        return text

    def predict(self, text: str) -> Layer1Result:
        processed = self._preprocess(text)
        X = self._vectorizer.transform([processed])
        pred_label = int(self._clf.predict(X)[0])
        proba = self._clf.predict_proba(X)[0]
        confidence = round(float(max(proba)) * 100, 1)
        verdict = self._LABELS[pred_label]

        feature_names = self._vectorizer.get_feature_names_out()
        bow_scores = X.toarray()[0]
        top_idx = bow_scores.argsort()[-5:][::-1]
        triggered = [feature_names[i] for i in top_idx if bow_scores[i] > 0]

        return Layer1Result(verdict=verdict, confidence=confidence, triggered_features=triggered)
