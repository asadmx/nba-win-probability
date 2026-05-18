"""FastAPI application entrypoint.

Wires together:
  - Health, games, predict, models routes
  - The PyTorch predictor (loaded once at startup, reused per request)
  - CORS for the React frontend
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_games, routes_health, routes_models, routes_predict
from app.websockets import simulator as ws_simulator
from app.config import settings
from app.ml.predictor import Predictor, set_predictor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code that runs on startup and shutdown.

    On startup we load the trained model from disk and stash it in the
    module-level singleton. Every API call reuses the same loaded model —
    no per-request I/O.
    """
    print(f"🚀 Starting {settings.app_name} ({settings.environment})")
    try:
        predictor = Predictor.load_default()
        set_predictor(predictor)
        print(f"   model loaded: {predictor.model_version}")
    except FileNotFoundError as e:
        print(f"   ⚠ no trained model on disk ({e}); /predict will fail")
    yield
    print("👋 Shutting down")


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router, prefix="/api")
app.include_router(routes_games.router, prefix="/api")
app.include_router(routes_predict.router, prefix="/api")
app.include_router(routes_models.router, prefix="/api")
app.include_router(ws_simulator.router)  # WebSocket — no /api prefix


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "NBA Win Probability Engine — see /docs for API"}