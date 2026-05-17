"""Prediction endpoint — single-shot inference for ad-hoc game states.

Live-game prediction during a real game happens over WebSockets (Phase 9).
This endpoint is for one-off calls — e.g., "what if the score was tied with
2 min left?" — useful for the dashboard's prediction explorer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.ml.predictor import Predictor, get_predictor
from app.schemas.predict import PredictRequest, PredictResponse

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("", response_model=PredictResponse)
def predict(
    req: PredictRequest,
    predictor: Predictor = Depends(get_predictor),
) -> PredictResponse:
    """Predict P(home_wins) for one game-state snapshot."""
    home_prob = predictor.predict_one(req.model_dump())
    return PredictResponse(
        home_win_prob=home_prob,
        away_win_prob=1.0 - home_prob,
        model_version=predictor.model_version,
    )