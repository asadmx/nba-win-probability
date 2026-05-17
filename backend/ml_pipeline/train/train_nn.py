"""Train the PyTorch MLP on game-state features.

Training procedure:
  - Adam optimizer (lr=1e-3) — standard default
  - Binary cross-entropy loss (BCEWithLogitsLoss for stability)
  - Up to 30 epochs with early stopping (patience=5 on val log loss)
  - Save best checkpoint (not last) — the epoch with lowest val loss
  - StandardScaler fit on train only (no leakage)

Outputs:
  ml_pipeline/artifacts/nn_model.pt       — trained weights
  ml_pipeline/artifacts/nn_scaler.joblib  — feature scaler (needed at inference)
  ml_pipeline/artifacts/nn_metrics.json   — val metrics + training history

Run with:
    python -m ml_pipeline.train.train_nn
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

from app.ml.model import WinProbabilityMLP
from ml_pipeline.features.build_features import FEATURE_COLUMNS
from ml_pipeline.ingest.config import PROCESSED_DIR

console = Console()
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"

# Hyperparameters. Pulled out so they're easy to find for the writeup.
BATCH_SIZE = 512
LEARNING_RATE = 1e-3
MAX_EPOCHS = 30
PATIENCE = 5  # epochs without improvement before early stopping
DROPOUT = 0.2
HIDDEN_1 = 64
HIDDEN_2 = 32


def make_loader(X: np.ndarray, y: np.ndarray, batch_size: int, shuffle: bool) -> DataLoader:
    """Wrap numpy arrays in a PyTorch DataLoader for batched training."""
    ds = TensorDataset(
        torch.tensor(X, dtype=torch.float32),
        torch.tensor(y, dtype=torch.float32),
    )
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, num_workers=0)


def evaluate(model: WinProbabilityMLP, loader: DataLoader, loss_fn) -> tuple[float, float]:
    """Run one full pass of the val set. Returns (avg_loss, accuracy)."""
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    with torch.no_grad():
        for xb, yb in loader:
            logits = model(xb)
            loss = loss_fn(logits, yb)
            total_loss += loss.item() * xb.size(0)
            preds = (torch.sigmoid(logits) >= 0.5).float()
            total_correct += (preds == yb).sum().item()
            total_count += xb.size(0)
    return total_loss / total_count, total_correct / total_count


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Reproducibility — same seed, same results.
    torch.manual_seed(42)
    np.random.seed(42)

    console.print("[bold cyan]Loading features...[/bold cyan]")
    df = pd.read_parquet(PROCESSED_DIR / "features.parquet")
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    console.print(f"  train: {len(train):,} rows | val: {len(val):,} rows")

    X_train = train[FEATURE_COLUMNS].values.astype(np.float32)
    y_train = train["home_won"].values.astype(np.float32)
    X_val = val[FEATURE_COLUMNS].values.astype(np.float32)
    y_val = val["home_won"].values.astype(np.float32)

    # Scale features. CRITICAL: fit on train only.
    console.print("[cyan]Fitting feature scaler on train data...[/cyan]")
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)

    train_loader = make_loader(X_train_s, y_train, BATCH_SIZE, shuffle=True)
    val_loader = make_loader(X_val_s, y_val, BATCH_SIZE, shuffle=False)

    # Build model.
    model = WinProbabilityMLP(
        n_features=len(FEATURE_COLUMNS),
        hidden_1=HIDDEN_1,
        hidden_2=HIDDEN_2,
        dropout=DROPOUT,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # BCEWithLogitsLoss = sigmoid + binary cross-entropy, fused for numerical
    # stability. Use this instead of nn.BCELoss(sigmoid(logits), y).
    loss_fn = torch.nn.BCEWithLogitsLoss()

    n_params = sum(p.numel() for p in model.parameters())
    console.print(f"[cyan]Model has {n_params:,} parameters[/cyan]")

    # Training loop with early stopping.
    best_val_loss = float("inf")
    best_state: dict | None = None
    patience_counter = 0
    history: list[dict] = []

    console.print("\n[bold cyan]Training...[/bold cyan]")
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Epochs", total=MAX_EPOCHS)
        for epoch in range(1, MAX_EPOCHS + 1):
            # Train one epoch.
            model.train()
            running_loss = 0.0
            n_seen = 0
            for xb, yb in train_loader:
                optimizer.zero_grad()
                logits = model(xb)
                loss = loss_fn(logits, yb)
                loss.backward()
                optimizer.step()
                running_loss += loss.item() * xb.size(0)
                n_seen += xb.size(0)
            train_loss = running_loss / n_seen

            val_loss, val_acc = evaluate(model, val_loader, loss_fn)
            history.append({
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "val_acc": val_acc,
            })

            improved = val_loss < best_val_loss
            marker = " ★ best" if improved else ""
            console.print(
                f"  Epoch {epoch:>2d} · train_loss={train_loss:.4f} "
                f"· val_loss={val_loss:.4f} · val_acc={val_acc:.4f}{marker}"
            )

            if improved:
                best_val_loss = val_loss
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= PATIENCE:
                    console.print(
                        f"[yellow]Early stopping at epoch {epoch} "
                        f"(no improvement for {PATIENCE} epochs)[/yellow]"
                    )
                    progress.update(task, completed=MAX_EPOCHS)
                    break
            progress.advance(task)

    # Restore best weights (not last epoch — these may be overfit).
    assert best_state is not None
    model.load_state_dict(best_state)

    # Final eval on val with best weights.
    final_val_loss, final_val_acc = evaluate(model, val_loader, loss_fn)
    console.print(
        f"\n[bold green]Trained[/bold green]"
        f"\n  Best val log loss: {final_val_loss:.4f}"
        f"\n  Best val accuracy: {final_val_acc:.4f}"
    )

    # Save model + scaler.
    torch.save(model.state_dict(), ARTIFACTS_DIR / "nn_model.pt")
    joblib.dump(scaler, ARTIFACTS_DIR / "nn_scaler.joblib")

    metrics = {
        "model": "mlp",
        "val_log_loss": float(final_val_loss),
        "val_accuracy": float(final_val_acc),
        "n_parameters": int(n_params),
        "hyperparameters": {
            "batch_size": BATCH_SIZE,
            "learning_rate": LEARNING_RATE,
            "max_epochs": MAX_EPOCHS,
            "patience": PATIENCE,
            "dropout": DROPOUT,
            "hidden_1": HIDDEN_1,
            "hidden_2": HIDDEN_2,
        },
        "feature_columns": FEATURE_COLUMNS,
        "n_train": int(len(train)),
        "n_val": int(len(val)),
        "history": history,
    }
    (ARTIFACTS_DIR / "nn_metrics.json").write_text(json.dumps(metrics, indent=2))

    console.print(f"\n  Saved: nn_model.pt, nn_scaler.joblib, nn_metrics.json")


if __name__ == "__main__":
    main()