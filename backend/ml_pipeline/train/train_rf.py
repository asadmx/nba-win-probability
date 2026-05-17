"""Train a random forest baseline on game-state features.

Tree-based: captures non-linear interactions without us engineering them.
The gap between this and logreg tells us how much non-linearity is in the data.

Outputs:
  ml_pipeline/artifacts/rf.joblib
  ml_pipeline/artifacts/rf_metrics.json

Run with:
    python -m ml_pipeline.train.train_rf
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from rich.console import Console
from sklearn.ensemble import RandomForestClassifier

from ml_pipeline.features.build_features import FEATURE_COLUMNS
from ml_pipeline.ingest.config import PROCESSED_DIR

console = Console()

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    console.print("[bold cyan]Loading features...[/bold cyan]")
    df = pd.read_parquet(PROCESSED_DIR / "features.parquet")
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    console.print(f"  train: {len(train):,} rows | val: {len(val):,} rows")

    X_train = train[FEATURE_COLUMNS].values
    y_train = train["home_won"].values.astype(int)
    X_val = val[FEATURE_COLUMNS].values
    y_val = val["home_won"].values.astype(int)

    # No scaling needed — trees are scale-invariant.
    # max_depth caps overfitting; min_samples_leaf keeps trees from memorizing.
    # n_jobs=-1 uses all CPU cores in parallel.
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=50,
        n_jobs=-1,
        random_state=42,
        class_weight="balanced",
    )

    console.print("[cyan]Fitting random forest (200 trees, this takes 1-3 min)...[/cyan]")
    clf.fit(X_train, y_train)

    val_acc = clf.score(X_val, y_val)
    val_probs = clf.predict_proba(X_val)[:, 1]
    val_logloss = -np.mean(y_val * np.log(val_probs + 1e-9) + (1 - y_val) * np.log(1 - val_probs + 1e-9))

    console.print(f"\n[bold green]Trained[/bold green]")
    console.print(f"  Val accuracy:  {val_acc:.4f}")
    console.print(f"  Val log loss:  {val_logloss:.4f}")

    out = ARTIFACTS_DIR / "rf.joblib"
    joblib.dump(clf, out)

    metrics = {
        "model": "rf",
        "val_accuracy": float(val_acc),
        "val_log_loss": float(val_logloss),
        "n_train": int(len(train)),
        "n_val": int(len(val)),
        "feature_columns": FEATURE_COLUMNS,
    }
    (ARTIFACTS_DIR / "rf_metrics.json").write_text(json.dumps(metrics, indent=2))

    console.print(f"  Saved to: {out.name}")

    # Feature importance — analogous to logreg coefs.
    importances = pd.Series(clf.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
    console.print("\n[bold]Top features by importance:[/bold]")
    for name, val in importances.head(8).items():
        console.print(f"  {name:<32s} {val:.3f}")


if __name__ == "__main__":
    main()