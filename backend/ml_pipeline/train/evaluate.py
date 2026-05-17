"""Evaluate trained models on the validation set.

Reads both logreg.joblib and rf.joblib, computes:
  - overall accuracy, log loss, Brier score, ROC AUC
  - accuracy by time-remaining bucket (the most interesting metric)
  - calibration buckets (does "80% home" actually win 80% of the time?)

Run with:
    python -m ml_pipeline.train.evaluate
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from ml_pipeline.features.build_features import FEATURE_COLUMNS
from ml_pipeline.ingest.config import PROCESSED_DIR

console = Console()
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"


def evaluate_model(name: str, model, X: np.ndarray, y: np.ndarray, df_val: pd.DataFrame) -> dict:
    """Compute headline metrics + bucketed accuracy for one model."""
    probs = model.predict_proba(X)[:, 1]
    preds = (probs >= 0.5).astype(int)

    metrics = {
        "model": name,
        "accuracy": float(np.mean(preds == y)),
        "log_loss": float(log_loss(y, probs, labels=[0, 1])),
        "brier": float(brier_score_loss(y, probs)),
        "roc_auc": float(roc_auc_score(y, probs)),
    }

    # Accuracy by minutes-remaining bucket.
    # This is what tells you the model is actually working: accuracy should
    # climb from ~55% at game start to >95% in the final minute.
    df_eval = df_val.copy()
    df_eval["prob"] = probs
    df_eval["pred"] = preds
    df_eval["correct"] = preds == y
    df_eval["minutes_remaining"] = df_eval["seconds_remaining_game"] // 60

    buckets = [
        (0, 1, "final minute"),
        (1, 3, "1-3 min left"),
        (3, 6, "3-6 min left"),
        (6, 12, "1 quarter left"),
        (12, 24, "1-2 quarters left"),
        (24, 48, "2+ quarters left"),
    ]
    bucket_metrics = []
    for lo, hi, label in buckets:
        mask = (df_eval["minutes_remaining"] >= lo) & (df_eval["minutes_remaining"] < hi)
        if mask.sum() == 0:
            continue
        sub = df_eval[mask]
        bucket_metrics.append({
            "bucket": label,
            "n": int(mask.sum()),
            "accuracy": float(sub["correct"].mean()),
        })
    metrics["by_time_bucket"] = bucket_metrics

    # Calibration: split predictions into 10 deciles, see how often each
    # decile's predictions actually came true.
    df_eval["prob_decile"] = pd.cut(df_eval["prob"], bins=10, labels=False)
    cal = df_eval.groupby("prob_decile").agg(
        mean_predicted=("prob", "mean"),
        mean_actual=("correct", "mean"),  # not quite right, but proxy
        n=("prob", "size"),
    )
    # The right calibration metric: in each decile, what was the actual home-win rate?
    cal_actual = df_eval.groupby("prob_decile")["pred"].count()
    cal_pred_mean = df_eval.groupby("prob_decile")["prob"].mean()
    cal_actual_rate = df_eval.groupby("prob_decile").apply(
        lambda g: g["prob"].notna().mean()  # placeholder; real one below
    )
    # Correct calibration: mean predicted vs mean actual outcome per decile.
    df_eval["y_true"] = y
    real_cal = df_eval.groupby("prob_decile").agg(
        mean_pred=("prob", "mean"),
        mean_actual=("y_true", "mean"),
        n=("prob", "size"),
    )
    metrics["calibration"] = real_cal.reset_index().to_dict(orient="records")

    return metrics


def print_summary(all_metrics: list[dict]) -> None:
    table = Table(title="Model comparison on validation set")
    table.add_column("Model")
    table.add_column("Accuracy", justify="right")
    table.add_column("Log Loss", justify="right")
    table.add_column("Brier", justify="right")
    table.add_column("ROC AUC", justify="right")
    for m in all_metrics:
        table.add_row(
            m["model"],
            f"{m['accuracy']:.4f}",
            f"{m['log_loss']:.4f}",
            f"{m['brier']:.4f}",
            f"{m['roc_auc']:.4f}",
        )
    console.print(table)

    # Accuracy by time bucket — the killer chart.
    console.print("\n[bold]Accuracy by time remaining:[/bold]")
    bucket_table = Table()
    bucket_table.add_column("Time bucket")
    for m in all_metrics:
        bucket_table.add_column(m["model"], justify="right")
    bucket_labels = [b["bucket"] for b in all_metrics[0]["by_time_bucket"]]
    for label in bucket_labels:
        row = [label]
        for m in all_metrics:
            b = next(b for b in m["by_time_bucket"] if b["bucket"] == label)
            row.append(f"{b['accuracy']:.3f} (n={b['n']:,})")
        bucket_table.add_row(*row)
    console.print(bucket_table)

    # Calibration summary
    console.print("\n[bold]Calibration (logreg):[/bold]")
    logreg_cal = next(m for m in all_metrics if m["model"] == "logreg")["calibration"]
    cal_table = Table()
    cal_table.add_column("Predicted P(home)")
    cal_table.add_column("Actual rate")
    cal_table.add_column("N")
    for row in logreg_cal:
        cal_table.add_row(
            f"{row['mean_pred']:.3f}",
            f"{row['mean_actual']:.3f}",
            f"{int(row['n']):,}",
        )
    console.print(cal_table)


def main() -> None:
    console.print("[bold cyan]Loading val set + models...[/bold cyan]")
    df = pd.read_parquet(PROCESSED_DIR / "features.parquet")
    val = df[df["split"] == "val"].copy()

    X_val = val[FEATURE_COLUMNS].values
    y_val = val["home_won"].values.astype(int)

    logreg = joblib.load(ARTIFACTS_DIR / "logreg.joblib")
    rf = joblib.load(ARTIFACTS_DIR / "rf.joblib")

    # The PyTorch model needs the feature scaler applied separately,
    # and it returns torch tensors. Wrap it in a sklearn-like interface.
    import torch
    from app.ml.model import load_checkpoint

    nn_scaler = joblib.load(ARTIFACTS_DIR / "nn_scaler.joblib")
    nn_model = load_checkpoint(ARTIFACTS_DIR / "nn_model.pt", n_features=len(FEATURE_COLUMNS))

    class NNWrapper:
        """sklearn-compatible interface so evaluate_model() works unchanged."""
        def predict_proba(self, X: np.ndarray) -> np.ndarray:
            X_scaled = nn_scaler.transform(X)
            with torch.no_grad():
                logits = nn_model(torch.tensor(X_scaled, dtype=torch.float32))
                probs = torch.sigmoid(logits).numpy()
            # Match sklearn's predict_proba shape: (n, 2) with [P(0), P(1)]
            return np.column_stack([1 - probs, probs])

    nn_wrapper = NNWrapper()

    console.print(f"  val: {len(val):,} rows · {val['game_id'].nunique():,} games\n")

    all_metrics = [
        evaluate_model("logreg", logreg, X_val, y_val, val),
        evaluate_model("rf", rf, X_val, y_val, val),
        evaluate_model("nn", nn_wrapper, X_val, y_val, val),
    ]
    print_summary(all_metrics)


if __name__ == "__main__":
    main()