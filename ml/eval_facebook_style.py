"""
Evaluate PhilVerify classifiers on the custom Facebook-style claim set.

This file intentionally keeps the Facebook-style evaluation split separate
from the training dataset. It answers: "How does the NLP classifier behave on
short, informal social-media claims?"

Usage:
    cd PhilVerify
    python -m ml.eval_facebook_style
    python -m ml.eval_facebook_style --csv ml/data/eval/facebook_style_claims.csv
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.bow_classifier import BoWClassifier
from ml.combined_dataset import LABEL_NAMES, get_split
from ml.lda_analysis import LDAFeatureClassifier
from ml.naive_bayes_classifier import NaiveBayesClassifier

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CSV = Path(__file__).parent / "data" / "eval" / "facebook_style_claims.csv"
LABEL_LIST = [LABEL_NAMES[i] for i in sorted(LABEL_NAMES)]


@dataclass
class EvalSample:
    text: str
    label: int
    label_name: str
    source_url: str
    language: str
    notes: str


def load_eval_csv(path: Path) -> list[EvalSample]:
    required = {"text", "label", "label_name", "source_url", "language", "notes"}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns in {path}: {sorted(missing)}")

        samples: list[EvalSample] = []
        for row_num, row in enumerate(reader, start=2):
            text = (row["text"] or "").strip()
            label = int(row["label"])
            if not text:
                raise ValueError(f"Row {row_num}: text is required")
            if label not in LABEL_NAMES:
                raise ValueError(f"Row {row_num}: label must be one of {sorted(LABEL_NAMES)}")
            expected = LABEL_NAMES[label]
            if row["label_name"].strip() != expected:
                raise ValueError(
                    f"Row {row_num}: label_name must be {expected!r} for label {label}"
                )
            samples.append(
                EvalSample(
                    text=text,
                    label=label,
                    label_name=expected,
                    source_url=(row["source_url"] or "").strip(),
                    language=(row["language"] or "").strip(),
                    notes=(row["notes"] or "").strip(),
                )
            )
    return samples


def evaluate_classifier(name: str, clf, samples: list[EvalSample]) -> dict:
    true_labels: list[str] = []
    pred_labels: list[str] = []
    for sample in samples:
        result = clf.predict(sample.text)
        true_labels.append(LABEL_NAMES[sample.label])
        pred_labels.append(result.verdict)

    print(f"\n{'=' * 70}")
    print(f"  {name} on Facebook-style claims")
    print(f"{'=' * 70}")
    print(classification_report(true_labels, pred_labels, labels=LABEL_LIST, zero_division=0))

    print("Confusion matrix (rows = true, cols = predicted):")
    print(f"  {'':14}", "  ".join(f"{lbl[:6]:>6}" for lbl in LABEL_LIST))
    cm = confusion_matrix(true_labels, pred_labels, labels=LABEL_LIST)
    for row_label, row in zip(LABEL_LIST, cm):
        print(f"  {row_label:<14}", "  ".join(f"{v:>6}" for v in row))

    return {"name": name, "accuracy": accuracy_score(true_labels, pred_labels)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate classifiers on the custom Facebook-style claim set"
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument(
        "--skip-lda",
        action="store_true",
        help="Skip LDA feature classifier if you want a faster run",
    )
    args = parser.parse_args()

    eval_samples = load_eval_csv(args.csv)
    train_samples, _ = get_split(train_ratio=args.train_ratio, seed=args.seed)
    logger.info("Train samples: %d | Facebook-style eval samples: %d", len(train_samples), len(eval_samples))

    results: list[dict] = []
    results.append(evaluate_classifier("BoW + LogReg", BoWClassifier(train_samples), eval_samples))
    results.append(evaluate_classifier("TF-IDF + Naive Bayes", NaiveBayesClassifier(train_samples), eval_samples))
    if not args.skip_lda:
        results.append(evaluate_classifier("LDA features + LogReg", LDAFeatureClassifier(train_samples), eval_samples))

    print(f"\n{'=' * 70}")
    print("  Summary")
    print(f"{'=' * 70}")
    for result in results:
        print(f"  {result['name']:<32} {result['accuracy'] * 100:>6.1f}%")


if __name__ == "__main__":
    main()
