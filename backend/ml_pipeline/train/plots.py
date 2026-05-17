"""Generate calibration + confusion plots for the trained models."""
from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from rich.console import Console
from sklearn.metrics import confusion_matrix

from app.ml.model import load_checkpoint
from ml_pipeline.features.build_features import FEATURE_COLUMNS
from ml_pipeline.ingest.config import PROCESSED_DIR

console = Console()
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"

BG_DARK = "#0B0D12"
BG_PANEL = "#15171F"
BORDER = "#2A2E3D"
TEXT_PRIMARY = "#E8EAF0"
TEXT_SECONDARY = "#7A7F8E"


def predict_nn(X):
    scaler = joblib.load(ARTIFACTS_DIR / "nn_scaler.joblib")
    model = load_checkpoint(ARTIFACTS_DIR / "nn_model.pt", n_features=len(FEATURE_COLUMNS))
    Xs = scaler.transform(X)
    with torch.no_grad():
        logits = model(torch.tensor(Xs, dtype=torch.float32))
        return torch.sigmoid(logits).numpy()


def plot_calibration(probs_dict, y, out_path):
    fig, ax = plt.subplots(figsize=(7, 7), facecolor=BG_DARK)
    ax.set_facecolor(BG_PANEL)
    ax.plot([0, 1], [0, 1], "--", color=TEXT_SECONDARY, linewidth=1, label="perfect")

    colors = {"logreg": "#22C55E", "rf": "#F59E0B", "nn": "#3B82F6"}
    for name, probs in probs_dict.items():
        bins = np.linspace(0, 1, 11)
        bin_idx = np.clip(np.digitize(probs, bins) - 1, 0, 9)
        mean_pred = []
        mean_actual = []
        for b in range(10):
            mask = bin_idx == b
            if mask.sum() == 0:
                continue
            mean_pred.append(probs[mask].mean())
            mean_actual.append(y[mask].mean())
        ax.plot(mean_pred, mean_actual, marker="o", label=name,
                color=colors.get(name, TEXT_PRIMARY), linewidth=2, markersize=8)

    ax.set_xlabel("Predicted P(home wins)", color=TEXT_PRIMARY)
    ax.set_ylabel("Actual P(home wins)", color=TEXT_PRIMARY)
    ax.set_title("Calibration on test set", color=TEXT_PRIMARY, fontsize=14, pad=15)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.2, color=TEXT_SECONDARY)
    ax.tick_params(colors=TEXT_SECONDARY)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    legend = ax.legend(loc="upper left", facecolor=BG_PANEL, edgecolor=BORDER)
    for text in legend.get_texts():
        text.set_color(TEXT_PRIMARY)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=BG_DARK)
    plt.close()
    console.print(f"  saved: {out_path.name}")


def plot_confusion(probs, y, name, out_path):
    preds = (probs >= 0.5).astype(int)
    cm = confusion_matrix(y, preds)
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    fig, ax = plt.subplots(figsize=(6, 6), facecolor=BG_DARK)
    ax.set_facecolor(BG_PANEL)
    ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1)

    for i in range(2):
        for j in range(2):
            count = cm[i, j]
            pct = cm_norm[i, j]
            text_color = "white" if pct > 0.5 else "#1F2230"
            label = f"{count:,}\n({pct:.1%})"
            ax.text(j, i, label, ha="center", va="center", color=text_color, fontsize=12)

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Predict away win", "Predict home win"], color=TEXT_PRIMARY)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Actual away win", "Actual home win"], color=TEXT_PRIMARY)
    ax.set_title(f"Confusion matrix: {name}", color=TEXT_PRIMARY, fontsize=14, pad=15)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=BG_DARK)
    plt.close()
    console.print(f"  saved: {out_path.name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["val", "test"], default="test")
    args = parser.parse_args()

    console.print(f"[bold cyan]Loading {args.split} set...[/bold cyan]")
    df = pd.read_parquet(PROCESSED_DIR / "features.parquet")
    eval_df = df[df["split"] == args.split]
    X = eval_df[FEATURE_COLUMNS].values
    y = eval_df["home_won"].values.astype(int)
    console.print(f"  {len(eval_df):,} rows, {eval_df['game_id'].nunique():,} games\n")

    console.print("[cyan]Computing predictions...[/cyan]")
    logreg = joblib.load(ARTIFACTS_DIR / "logreg.joblib")
    rf = joblib.load(ARTIFACTS_DIR / "rf.joblib")

    probs = {
        "logreg": logreg.predict_proba(X)[:, 1],
        "rf": rf.predict_proba(X)[:, 1],
        "nn": predict_nn(X),
    }

    console.print("[cyan]Generating plots...[/cyan]")
    plot_calibration(probs, y, ARTIFACTS_DIR / "plot_calibration.png")
    plot_confusion(probs["nn"], y, "PyTorch MLP", ARTIFACTS_DIR / "plot_confusion.png")
    console.print("[bold green]Done[/bold green]")


if __name__ == "__main__":
    main()