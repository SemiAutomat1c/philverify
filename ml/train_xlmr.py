#!/usr/bin/env python3
"""
PhilVerify — XLM-RoBERTa Fine-tuning Script (Phase 10)

Fine-tunes xlm-roberta-base on the PhilVerify labeled dataset (ml/dataset.py).
Saves the checkpoint to ml/models/xlmr_model/ for use by XLMRobertaClassifier.

Usage:
    cd PhilVerify/
    source venv/bin/activate
    python ml/train_xlmr.py [--epochs N] [--lr FLOAT] [--batch-size N] [--no-freeze]

Typical runtime (CPU, MacBook M1):  ~8–12 minutes for 5 epochs on 100 samples
Typical runtime (GPU/MPS):          ~1–2 minutes
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR  = Path(__file__).parent / "models" / "xlmr_model"
BASE_MODEL  = "xlm-roberta-base"
MAX_LENGTH  = 256


# ── PyTorch Dataset ───────────────────────────────────────────────────────────

class PhilVerifyDataset:
    def __init__(self, samples, tokenizer) -> None:
        self.encodings = tokenizer(
            [s.text for s in samples],
            truncation=True,
            padding="max_length",
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )
        import torch
        self.labels = torch.tensor([s.label for s in samples], dtype=torch.long)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int):
        return {
            "input_ids":      self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "labels":         self.labels[idx],
        }


# ── Freeze helpers ────────────────────────────────────────────────────────────

def freeze_lower_layers(model, keep_top_n: int = 2) -> int:
    """
    Freeze all encoder layers except the top `keep_top_n`.
    The classification head is always kept trainable.
    Returns the number of frozen parameters.
    """
    frozen = 0
    total_layers = len(model.roberta.encoder.layer)
    unfreeze_from = total_layers - keep_top_n

    for i, layer in enumerate(model.roberta.encoder.layer):
        if i < unfreeze_from:
            for p in layer.parameters():
                p.requires_grad = False
                frozen += p.numel()

    # Also freeze embeddings
    for p in model.roberta.embeddings.parameters():
        p.requires_grad = False
        frozen += p.numel()

    logger.info(
        "Frozen %d / %d encoder layers (keeping top %d + classifier head). "
        "%d params frozen.",
        unfreeze_from, total_layers, keep_top_n, frozen,
    )
    return frozen


# ── Metrics ───────────────────────────────────────────────────────────────────

def evaluate(model, loader, device) -> dict:
    import torch
    model.eval()
    all_preds, all_labels = [], []
    total_loss = 0.0
    n_batches  = 0
    loss_fn    = torch.nn.CrossEntropyLoss()

    with torch.no_grad():
        for batch in loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            labels  = batch["labels"]
            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
            )
            loss = loss_fn(outputs.logits, labels)
            total_loss += loss.item()
            preds = outputs.logits.argmax(dim=-1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())
            n_batches += 1

    correct = sum(p == l for p, l in zip(all_preds, all_labels))
    return {
        "loss":     round(total_loss / max(n_batches, 1), 4),
        "accuracy": round(correct / max(len(all_labels), 1) * 100, 1),
    }


# ── Main training loop ────────────────────────────────────────────────────────

def train(
    epochs:     int   = 5,
    lr:         float = 2e-5,
    batch_size: int   = 8,
    freeze:     bool  = True,
    keep_top_n: int   = 2,
    seed:       int   = 42,
) -> None:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from ml.combined_dataset import get_split, class_weights, LABEL_NAMES, NUM_LABELS

    # ── Reproducibility ───────────────────────────────────────────────────────
    torch.manual_seed(seed)

    # ── Device ────────────────────────────────────────────────────────────────
    if torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    logger.info("Device: %s", device)

    # ── Data ──────────────────────────────────────────────────────────────────
    train_samples, val_samples = get_split(train_ratio=0.8, seed=seed)
    logger.info("Dataset: %d train / %d val", len(train_samples), len(val_samples))

    logger.info("Loading tokenizer: %s …", BASE_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    train_ds = PhilVerifyDataset(train_samples, tokenizer)
    val_ds   = PhilVerifyDataset(val_samples,   tokenizer)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False)

    # ── Model ─────────────────────────────────────────────────────────────────
    logger.info("Loading model: %s …", BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=NUM_LABELS,
        id2label=LABEL_NAMES,
        label2id={v: k for k, v in LABEL_NAMES.items()},
    )
    if freeze:
        freeze_lower_layers(model, keep_top_n=keep_top_n)
    model.to(device)

    total_params     = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(
        "Parameters: %d total / %d trainable (%.1f%%)",
        total_params, trainable_params, trainable_params / total_params * 100,
    )

    # ── Class-weighted loss ───────────────────────────────────────────────────
    weights = torch.tensor(
        class_weights(train_samples), dtype=torch.float
    ).to(device)
    logger.info("Class weights: %s", [round(w, 3) for w in weights.tolist()])

    # Loss function with class weights (used in training loop)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)

    # ── Optimiser ─────────────────────────────────────────────────────────────
    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr,
        weight_decay=0.01,
    )

    # Linear warm-up + decay
    total_steps   = epochs * len(train_loader)
    warmup_steps  = max(1, total_steps // 10)

    def lr_lambda(step: int) -> float:
        if step < warmup_steps:
            return step / warmup_steps
        progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
        return max(0.05, 1.0 - progress)

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # ── Training ──────────────────────────────────────────────────────────────
    best_val_acc   = 0.0
    best_epoch     = 0
    global_step    = 0

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        t0 = time.time()

        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            labels = batch["labels"]
            optimizer.zero_grad()
            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
            )
            loss = loss_fn(outputs.logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                filter(lambda p: p.requires_grad, model.parameters()), 1.0
            )
            optimizer.step()
            scheduler.step()
            epoch_loss += loss.item()
            global_step += 1

        avg_loss = epoch_loss / max(len(train_loader), 1)
        val_metrics = evaluate(model, val_loader, device)
        elapsed = time.time() - t0

        logger.info(
            "Epoch %d/%d  train_loss=%.4f  val_loss=%.4f  val_acc=%.1f%%  (%.0fs)",
            epoch, epochs, avg_loss,
            val_metrics["loss"], val_metrics["accuracy"], elapsed,
        )

        if val_metrics["accuracy"] >= best_val_acc:
            best_val_acc = val_metrics["accuracy"]
            best_epoch   = epoch
            # Save best checkpoint so far
            _save(model, tokenizer)

    logger.info(
        "Training complete. Best val_acc=%.1f%% at epoch %d. Saved → %s",
        best_val_acc, best_epoch, OUTPUT_DIR,
    )


def _save(model, tokenizer) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    logger.info("Checkpoint saved to %s", OUTPUT_DIR)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fine-tune XLM-RoBERTa for PhilVerify misinformation classification",
    )
    p.add_argument("--epochs",     type=int,   default=5,    help="Training epochs (default: 5)")
    p.add_argument("--lr",         type=float, default=2e-5, help="Learning rate (default: 2e-5)")
    p.add_argument("--batch-size", type=int,   default=8,    help="Batch size (default: 8)")
    p.add_argument("--keep-top-n", type=int,   default=2,    help="Unfrozen encoder layers (default: 2)")
    p.add_argument("--no-freeze",  action="store_true",      help="Train all layers (slower, needs more data)")
    p.add_argument("--seed",       type=int,   default=42,   help="Random seed (default: 42)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        freeze=not args.no_freeze,
        keep_top_n=args.keep_top_n,
        seed=args.seed,
    )
