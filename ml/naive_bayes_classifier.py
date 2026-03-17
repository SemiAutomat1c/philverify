"""
PhilVerify — TF-IDF + Naive Bayes Classifier (Layer 1)

MultinomialNB with TF-IDF features. Trains on the provided sample split so that
eval comparisons are fair (same train/val split as transformer models).
Supports optional WordNet lemmatization to measure its effect on Filipino/Taglish text.
"""
import logging

logger = logging.getLogger(__name__)


def _lemmatize_tokens(tokens: list[str]) -> list[str]:
    """
    Lemmatize tokens with POS-aware WordNet lemmatization.
    Downloads required NLTK data on first call. Falls back to identity on any error.
    Note: WordNet is English-biased — Tagalog tokens are returned unchanged.
    """
    try:
        import nltk
        from nltk.corpus import wordnet
        from nltk.stem import WordNetLemmatizer

        for resource, path in [
            ("wordnet", "corpora/wordnet"),
            ("averaged_perceptron_tagger_eng", "taggers/averaged_perceptron_tagger_eng"),
        ]:
            try:
                nltk.data.find(path)
            except LookupError:
                nltk.download(resource, quiet=True)

        def _wn_pos(tag: str) -> str:
            if tag.startswith("J"):
                return wordnet.ADJ
            if tag.startswith("V"):
                return wordnet.VERB
            if tag.startswith("R"):
                return wordnet.ADV
            return wordnet.NOUN

        lemmatizer = WordNetLemmatizer()
        tagged = nltk.pos_tag(tokens)
        return [lemmatizer.lemmatize(w, _wn_pos(t)) for w, t in tagged]
    except Exception as exc:
        logger.debug("Lemmatization skipped (%s) — returning raw tokens", exc)
        return tokens


# Import shared result type
from ml.tfidf_classifier import Layer1Result  # noqa: E402


class NaiveBayesClassifier:
    """
    TF-IDF + MultinomialNB classifier. Same predict() interface as TFIDFClassifier.

    Args:
        train_samples: list[Sample] from ml.dataset. If None, uses the full 100-sample dataset.
        lemmatize:     apply WordNet lemmatization before vectorization.
    """

    _LABELS = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}

    def __init__(self, train_samples=None, lemmatize: bool = False):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB

        self._lemmatize = lemmatize

        if train_samples is None:
            from ml.dataset import get_dataset
            train_samples = get_dataset()

        texts = [self._preprocess(s.text) for s in train_samples]
        labels = [s.label for s in train_samples]

        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=1000,
            sublinear_tf=True,
        )
        X = self._vectorizer.fit_transform(texts)

        self._clf = MultinomialNB(alpha=1.0)
        self._clf.fit(X, labels)
        logger.info(
            "NaiveBayesClassifier trained on %d samples (lemmatize=%s)",
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
        tfidf_scores = X.toarray()[0]
        top_idx = tfidf_scores.argsort()[-5:][::-1]
        triggered = [feature_names[i] for i in top_idx if tfidf_scores[i] > 0]

        return Layer1Result(verdict=verdict, confidence=confidence, triggered_features=triggered)
