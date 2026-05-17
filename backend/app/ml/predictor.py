"""Production model predictor — loads model + scaler once at startup.

Used by the FastAPI app. Lifecycle:
  - On startup, FastAPI's lifespan calls Predictor.load_default()
  - Each request calls predictor.predict(features) — no I/O, no disk
  - On shutdown, the predictor is garbage-collected

The Predictor class is the boundary between training artifacts (PyTorch
state dict + sklearn scaler on disk) and the live API. If we change the
model architecture, only this file needs to know — the rest of the API
just calls predict().
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import torch

from app.ml.model import WinProbabilityMLP, load_checkpoint

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "ml_pipeline" / "artifacts"

# Feature columns the model expects, in order. Must match what the training
# script saved — we read it from the metrics JSON to avoid drift.
FEATURE_ORDER: list[str] = [
    "score_margin",
    "seconds_remaining_game",
    "seconds_remaining_period",
    "period",
    "is_overtime",
    "is_clutch",
    "home_has_possession",
    "home_fouls_period",
    "away_fouls_period",
    "home_in_bonus",
    "away_in_bonus",
    "momentum_5",
    "recent_scoring_run",
    "margin_x_logtime",
    "margin_per_second_remaining",
    "abs_margin",
]


class Predictor:
    """Wraps the trained model + scaler. Thread-safe for read-only inference."""

    def __init__(self, model: WinProbabilityMLP, scaler, model_version: str) -> None:
        self.model = model
        self.scaler = scaler
        self.model_version = model_version

    @classmethod
    def load_default(cls) -> "Predictor":
        """Load the default trained PyTorch model from artifacts/."""
        model = load_checkpoint(ARTIFACTS_DIR / "nn_model.pt", n_features=len(FEATURE_ORDER))
        scaler = joblib.load(ARTIFACTS_DIR / "nn_scaler.joblib")

        # Read training metadata to construct a version string.
        metrics_path = ARTIFACTS_DIR / "nn_metrics.json"
        if metrics_path.exists():
            meta = json.loads(metrics_path.read_text())
            acc = meta.get("val_accuracy", 0.0)
            version = f"mlp-acc{acc:.3f}"
        else:
            version = "mlp-unknown"

        return cls(model=model, scaler=scaler, model_version=version)

    def predict_one(self, features: dict) -> float:
        """Predict P(home_wins) for a single game state.

        `features` is a dict keyed by FEATURE_ORDER names. Missing keys raise.
        Returns a float in [0, 1].
        """
        try:
            row = [features[name] for name in FEATURE_ORDER]
        except KeyError as e:
            raise ValueError(f"Missing feature: {e}") from e

        X = np.array([row], dtype=np.float32)
        X_scaled = self.scaler.transform(X)
        with torch.no_grad():
            logits = self.model(torch.tensor(X_scaled, dtype=torch.float32))
            probs = torch.sigmoid(logits).numpy()
        return float(probs[0])

    def predict_batch(self, rows: list[dict]) -> list[float]:
        """Same as predict_one but vectorized for multiple states.

        Reused by the WebSocket layer in Phase 9 — one tensor pass for many
        clients watching the same game tick is much faster than N separate
        calls.
        """
        X = np.array(
            [[r[name] for name in FEATURE_ORDER] for r in rows],
            dtype=np.float32,
        )
        X_scaled = self.scaler.transform(X)
        with torch.no_grad():
            logits = self.model(torch.tensor(X_scaled, dtype=torch.float32))
            probs = torch.sigmoid(logits).numpy()
        return probs.tolist()


# Module-level handle. Populated by FastAPI's lifespan hook at startup.
# Routes import this and use it directly. Single source of truth.
_predictor: Optional[Predictor] = None


def get_predictor() -> Predictor:
    """FastAPI dependency. Returns the loaded predictor or raises if not ready."""
    if _predictor is None:
        raise RuntimeError(
            "Predictor not initialized. Check that FastAPI's lifespan ran."
        )
    return _predictor


def set_predictor(p: Predictor) -> None:
    """Called by FastAPI lifespan during startup."""
    global _predictor
    _predictor = p