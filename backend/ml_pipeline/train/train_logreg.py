"""Train a logistic regression baseline on game-state features.

The model is intentionally simple: linear, fast, interpretable.
Coefficients tell us which features matter and how much.

Outputs:
  ml_pipeline/artifacts/logreg.joblib     — trained pipeline (scaler + model)
  ml_pipeline/artifacts/logreg_metrics.json — val-set metrics

Run with:
    python -m ml_pipeline.train.train_logreg
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from rich.console import Console
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

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

    # Pipeline: standardize features then fit linear model.
    # CRITICAL: the scaler fits on train data only. If it fit on val/test
    # too, statistics from the future would leak into the model.
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            C=1.0,
            solver="lbfgs",
            random_state=42,
        )),
    ])

    console.print("[cyan]Fitting logistic regression...[/cyan]")
    pipe.fit(X_train, y_train)

    # Quick sanity metrics here; the heavy evaluation is in evaluate.py.
    val_acc = pipe.score(X_val, y_val)
    val_probs = pipe.predict_proba(X_val)[:, 1]
    val_logloss = -np.mean(y_val * np.log(val_probs + 1e-9) + (1 - y_val) * np.log(1 - val_probs + 1e-9))

    console.print(f"\n[bold green]Trained[/bold green]")
    console.print(f"  Val accuracy:  {val_acc:.4f}")
    console.print(f"  Val log loss:  {val_logloss:.4f}")

    # Save pipeline (scaler + model in one artifact).
    out = ARTIFACTS_DIR / "logreg.joblib"
    joblib.dump(pipe, out)

    metrics = {
        "model": "logreg",
        "val_accuracy": float(val_acc),
        "val_log_loss": float(val_logloss),
        "n_train": int(len(train)),
        "n_val": int(len(val)),
        "feature_columns": FEATURE_COLUMNS,
    }
    (ARTIFACTS_DIR / "logreg_metrics.json").write_text(json.dumps(metrics, indent=2))

    console.print(f"  Saved to: {out.name}")

    # Print coefficients — interpretability is the whole point of logreg.
    clf = pipe.named_steps["clf"]
    coefs = pd.Series(clf.coef_[0], index=FEATURE_COLUMNS).sort_values(key=abs, ascending=False)
    console.print("\n[bold]Top features by |coefficient| (after scaling):[/bold]")
    for name, val in coefs.head(8).items():
        sign = "+" if val > 0 else "-"
        console.print(f"  {sign} {name:<32s} {val:+.3f}")


if __name__ == "__main__":
    main()