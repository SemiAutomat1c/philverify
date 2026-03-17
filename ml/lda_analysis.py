"""
PhilVerify — LDA Topic Analysis + LDA Feature Classifier (Layer 1)

Two responsibilities:

  1. run_topic_analysis(samples, n_topics)
       Fits LDA on training texts, prints top-N words per topic and the dominant
       topic distribution per class (Credible / Unverified / Likely Fake).
       Call directly to explore what topics the model discovers.

  2. LDAFeatureClassifier
       Concatenates LDA topic distribution features with TF-IDF features and feeds
       the combined vector into LogisticRegression. Same predict() interface as
       TFIDFClassifier — slots directly into eval.py.

Usage:
    python -m ml.lda_analysis          # standalone topic analysis
    python -m ml.eval                  # compare LDAFeatureClassifier against others
"""
import logging

import numpy as np
import scipy.sparse as sp

from ml.dataset import LABEL_NAMES, get_split
from ml.naive_bayes_classifier import _lemmatize_tokens
from ml.tfidf_classifier import Layer1Result

logger = logging.getLogger(__name__)

_LABELS = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}


# ── Standalone topic analysis ──────────────────────────────────────────────────

def run_topic_analysis(
    samples,
    n_topics: int = 5,
    n_top_words: int = 10,
) -> None:
    """
    Fit LDA on samples and print:
    - Top-N words per topic
    - Mean topic distribution per class label
    """
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer

    texts = [s.text.lower() for s in samples]
    labels = [s.label for s in samples]

    # LDA requires raw counts (not TF-IDF)
    vectorizer = CountVectorizer(max_features=500, stop_words="english")
    X = vectorizer.fit_transform(texts)
    vocab = vectorizer.get_feature_names_out()

    lda = LatentDirichletAllocation(
        n_components=n_topics, random_state=42, max_iter=30, learning_method="batch"
    )
    doc_topics = lda.fit_transform(X)  # (n_samples, n_topics)

    print(f"\n{'='*62}")
    print(f"  LDA Topic Analysis  ({n_topics} topics, {len(samples)} samples)")
    print(f"{'='*62}")

    for i, topic_vec in enumerate(lda.components_):
        top_idx = topic_vec.argsort()[-n_top_words:][::-1]
        top_words = [vocab[j] for j in top_idx]
        print(f"\n  Topic {i + 1}: {', '.join(top_words)}")

    print(f"\n  Per-class dominant topics:")
    for label_id, label_name in sorted(LABEL_NAMES.items()):
        class_idx = [i for i, l in enumerate(labels) if l == label_id]
        if not class_idx:
            continue
        mean_dist = doc_topics[class_idx].mean(axis=0)
        top2 = mean_dist.argsort()[-2:][::-1]
        topic_str = "  ".join(f"T{d+1}:{mean_dist[d]:.2f}" for d in top2)
        print(f"  {label_name:<14}  {topic_str}")


# ── LDA Feature Classifier ─────────────────────────────────────────────────────

class LDAFeatureClassifier:
    """
    LDA topic distribution + TF-IDF features → LogisticRegression.

    Feature vector = sparse_hstack([tfidf_features, lda_topic_distribution])

    Args:
        train_samples: list[Sample]. If None, uses the full 100-sample dataset.
        n_topics:      number of LDA topics (default 5).
        lemmatize:     apply WordNet lemmatization before vectorization.
    """

    def __init__(self, train_samples=None, n_topics: int = 5, lemmatize: bool = False):
        from sklearn.decomposition import LatentDirichletAllocation
        from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
        from sklearn.linear_model import LogisticRegression

        self._lemmatize = lemmatize
        self._n_topics = n_topics

        if train_samples is None:
            from ml.dataset import get_dataset
            train_samples = get_dataset()

        texts = [self._preprocess(s.text) for s in train_samples]
        labels = [s.label for s in train_samples]

        # TF-IDF part
        self._tfidf = TfidfVectorizer(
            ngram_range=(1, 2), max_features=1000, sublinear_tf=True
        )
        X_tfidf = self._tfidf.fit_transform(texts)

        # LDA part (requires raw counts)
        self._count_vec = CountVectorizer(max_features=500)
        X_counts = self._count_vec.fit_transform(texts)
        self._lda = LatentDirichletAllocation(
            n_components=n_topics, random_state=42, max_iter=30, learning_method="batch"
        )
        X_lda = self._lda.fit_transform(X_counts)  # dense (n_samples, n_topics)

        # Combine: sparse TF-IDF + dense LDA → sparse
        X_combined = sp.hstack([X_tfidf, sp.csr_matrix(X_lda)])

        self._clf = LogisticRegression(max_iter=500, C=1.0, random_state=42)
        self._clf.fit(X_combined, labels)
        logger.info(
            "LDAFeatureClassifier trained on %d samples (n_topics=%d, lemmatize=%s)",
            len(texts), n_topics, lemmatize,
        )

    def _preprocess(self, text: str) -> str:
        text = text.lower()
        if self._lemmatize:
            return " ".join(_lemmatize_tokens(text.split()))
        return text

    def predict(self, text: str) -> Layer1Result:
        processed = self._preprocess(text)
        X_tfidf = self._tfidf.transform([processed])
        X_counts = self._count_vec.transform([processed])
        X_lda = self._lda.transform(X_counts)  # (1, n_topics)
        X_combined = sp.hstack([X_tfidf, sp.csr_matrix(X_lda)])

        pred_label = int(self._clf.predict(X_combined)[0])
        proba = self._clf.predict_proba(X_combined)[0]
        confidence = round(float(max(proba)) * 100, 1)
        verdict = _LABELS[pred_label]

        # Top TF-IDF features
        feature_names = self._tfidf.get_feature_names_out()
        tfidf_scores = X_tfidf.toarray()[0]
        top_idx = tfidf_scores.argsort()[-4:][::-1]
        triggered = [feature_names[i] for i in top_idx if tfidf_scores[i] > 0]

        # Prepend dominant topic label
        dominant_topic = int(X_lda[0].argmax()) + 1
        triggered.insert(0, f"lda_topic_{dominant_topic}")

        return Layer1Result(
            verdict=verdict,
            confidence=confidence,
            triggered_features=triggered[:5],
        )


# ── Direct run ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LDA topic analysis on PhilVerify dataset")
    parser.add_argument("--n-topics", type=int, default=5)
    parser.add_argument("--n-top-words", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train_samples, _ = get_split(seed=args.seed)
    run_topic_analysis(train_samples, n_topics=args.n_topics, n_top_words=args.n_top_words)
