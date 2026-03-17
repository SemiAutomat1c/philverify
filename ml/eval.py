"""
Evaluate all PhilVerify classifiers on the held-out validation split.

Prints per-class precision/recall/F1, confusion matrix, and a side-by-side
accuracy summary for all model variants:

  Classical (trained on train split):
    BoW + LogReg
    BoW + LogReg + Lemma
    TF-IDF + LogReg  (legacy SEED_DATA baseline)
    TF-IDF + NB
    TF-IDF + NB + Lemma
    LDA features + LogReg

  Transformer (loaded from saved checkpoints):
    XLM-RoBERTa
    Tagalog-RoBERTa
    Ensemble (XLM-R + Tagalog-RoBERTa)

Usage:
    cd PhilVerify
    python -m ml.eval
    python -m ml.eval --seed 42 --train-ratio 0.8 --skip-lda-analysis
"""
import argparse
import logging

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from ml.bow_classifier import BoWClassifier
from ml.dataset import LABEL_NAMES, get_split
from ml.ensemble_classifier import EnsembleClassifier
from ml.lda_analysis import LDAFeatureClassifier, run_topic_analysis
from ml.naive_bayes_classifier import NaiveBayesClassifier
from ml.tagalog_roberta_classifier import TagalogRobertaClassifier
from ml.tfidf_classifier import TFIDFClassifier
from ml.xlm_roberta_classifier import ModelNotFoundError, XLMRobertaClassifier

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

LABEL_LIST = [LABEL_NAMES[i] for i in sorted(LABEL_NAMES)]


def evaluate_classifier(name: str, clf, samples: list) -> dict:
    true_labels, pred_labels = [], []
    for s in samples:
        result = clf.predict(s.text)
        true_labels.append(LABEL_NAMES[s.label])
        pred_labels.append(result.verdict)

    print(f"\n{'='*62}")
    print(f"  {name}")
    print(f"{'='*62}")
    print(classification_report(true_labels, pred_labels, labels=LABEL_LIST, zero_division=0))

    print("Confusion matrix (rows = true, cols = predicted):")
    print(f"  {'':14}", "  ".join(f"{lbl[:6]:>6}" for lbl in LABEL_LIST))
    cm = confusion_matrix(true_labels, pred_labels, labels=LABEL_LIST)
    for row_label, row in zip(LABEL_LIST, cm):
        print(f"  {row_label:<14}", "  ".join(f"{v:>6}" for v in row))

    acc = accuracy_score(true_labels, pred_labels)
    return {"name": name, "accuracy": acc}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PhilVerify classifiers")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (must match training seed)")
    parser.add_argument("--train-ratio", type=float, default=0.8,
                        help="Train split ratio (must match training)")
    parser.add_argument("--skip-lda-analysis", action="store_true",
                        help="Skip the LDA topic analysis printout")
    args = parser.parse_args()

    train_samples, val_samples = get_split(train_ratio=args.train_ratio, seed=args.seed)
    logger.info(
        "Train: %d samples  |  Val: %d samples  (seed=%d, train_ratio=%.1f)",
        len(train_samples), len(val_samples), args.seed, args.train_ratio,
    )

    # ── LDA topic analysis (printed before classifier comparison) ────────────
    if not args.skip_lda_analysis:
        run_topic_analysis(train_samples)

    results: list[dict] = []

    # ── Classical baselines (all trained on train_samples for fair comparison) ─

    results.append(evaluate_classifier(
        "BoW + LogReg",
        BoWClassifier(train_samples),
        val_samples,
    ))

    results.append(evaluate_classifier(
        "BoW + LogReg + Lemma",
        BoWClassifier(train_samples, lemmatize=True),
        val_samples,
    ))

    # Legacy baseline (trains on internal SEED_DATA, not the split — included for reference)
    results.append(evaluate_classifier(
        "TF-IDF + LogReg  [legacy SEED_DATA]",
        TFIDFClassifier(),
        val_samples,
    ))

    results.append(evaluate_classifier(
        "TF-IDF + NB",
        NaiveBayesClassifier(train_samples),
        val_samples,
    ))

    results.append(evaluate_classifier(
        "TF-IDF + NB + Lemma",
        NaiveBayesClassifier(train_samples, lemmatize=True),
        val_samples,
    ))

    results.append(evaluate_classifier(
        "LDA features + LogReg",
        LDAFeatureClassifier(train_samples),
        val_samples,
    ))

    # ── Transformer models ───────────────────────────────────────────────────
    xlmr = None
    try:
        xlmr = XLMRobertaClassifier()
        results.append(evaluate_classifier("XLM-RoBERTa", xlmr, val_samples))
    except ModelNotFoundError:
        logger.warning("XLM-RoBERTa checkpoint not found — skipping")

    tl = None
    try:
        tl = TagalogRobertaClassifier()
        results.append(evaluate_classifier("Tagalog-RoBERTa", tl, val_samples))
    except ModelNotFoundError:
        logger.warning("Tagalog-RoBERTa checkpoint not found — skipping")

    if xlmr is not None and tl is not None:
        ensemble = EnsembleClassifier([xlmr, tl])
        results.append(evaluate_classifier(
            "Ensemble (XLM-R + Tagalog-RoBERTa)", ensemble, val_samples
        ))

    # ── Summary table ────────────────────────────────────────────────────────
    print(f"\n{'='*62}")
    print("  Summary")
    print(f"{'='*62}")
    print(f"  {'Model':<44} {'Accuracy':>8}")
    print(f"  {'-'*44} {'-'*8}")

    classical_done = False
    for r in results:
        is_transformer = any(
            kw in r["name"] for kw in ("XLM", "RoBERTa", "Tagalog", "Ensemble")
        )
        if is_transformer and not classical_done:
            print()  # blank separator between classical and transformer sections
            classical_done = True
        print(f"  {r['name']:<44} {r['accuracy'] * 100:>7.1f}%")

    best = max(results, key=lambda r: r["accuracy"])
    print(f"\n  Best: {best['name']}  ({best['accuracy'] * 100:.1f}%)")
    print()


if __name__ == "__main__":
    main()
