"""Model metadata endpoint — what's loaded, what version, what metrics."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.ml.predictor import Predictor, get_predictor

router = APIRouter(prefix="/models", tags=["models"])

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "ml_pipeline" / "artifacts"


class ModelInfo(BaseModel):
    name: str
    version: str
    val_accuracy: float | None
    val_log_loss: float | None
    n_parameters: int | None


@router.get("", response_model=list[ModelInfo])
def list_models(predictor: Predictor = Depends(get_predictor)) -> list[ModelInfo]:
    """Returns metadata for the currently-loaded production model."""
    metrics_path = ARTIFACTS_DIR / "nn_metrics.json"
    meta = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    return [
        ModelInfo(
            name="mlp",
            version=predictor.model_version,
            val_accuracy=meta.get("val_accuracy"),
            val_log_loss=meta.get("val_log_loss"),
            n_parameters=meta.get("n_parameters"),
        )
    ]