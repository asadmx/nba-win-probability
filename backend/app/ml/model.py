"""Neural network for NBA win probability prediction.

A small MLP (multi-layer perceptron) — the simplest deep model that
makes sense for tabular data. For 16 features and ~480K training rows,
anything fancier would overfit.

This module is imported by:
  - ml_pipeline/train/train_nn.py (training)
  - app/ml/predictor.py later (inference at serve time)

Keeping the architecture defined in one place prevents the classic
"trained with one architecture, served with another" production bug.
"""
from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn


class WinProbabilityMLP(nn.Module):
    """Simple feed-forward network: 16 → 64 → 32 → 1.

    Outputs a single probability via sigmoid. Inputs are assumed to be
    pre-normalized (the training script handles this with StandardScaler).

    Total parameters: ~2,500. Trains in 1-2 min on CPU. Easily fits in memory
    on any laptop. Designed for tabular data, not images/text.
    """

    def __init__(self, n_features: int = 16, hidden_1: int = 64, hidden_2: int = 32, dropout: float = 0.2) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden_1),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_1, hidden_2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_2, 1),
        )
        # We apply sigmoid in the loss-aware path manually; see forward().

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Returns logits (pre-sigmoid).

        We return logits, not probabilities, because BCEWithLogitsLoss is more
        numerically stable than BCELoss + sigmoid separately. Convert to
        probability with torch.sigmoid() when needed for display/evaluation.
        """
        return self.net(x).squeeze(-1)

    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Convenience method: returns probabilities (post-sigmoid)."""
        self.eval()
        with torch.no_grad():
            return torch.sigmoid(self.forward(x))


def load_checkpoint(path: Path | str, n_features: int = 16) -> WinProbabilityMLP:
    """Load a trained model from disk for inference.

    Used at FastAPI startup. Returns the model in eval mode, ready to predict.
    """
    model = WinProbabilityMLP(n_features=n_features)
    state = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    return model