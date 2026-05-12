"""FastAPI application entrypoint.

This is the file uvicorn loads when the server starts.
The `app` variable on line ~30 is what uvicorn looks for — that's why
we run `uvicorn app.main:app` (module: app.main, variable: app).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_health
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code that runs on startup and shutdown.

    Right now it just prints. Later, this is where we'll load the
    trained PyTorch model into memory — once at startup, not per
    request — so inference is fast.
    """
    print(f"🚀 Starting {settings.app_name} ({settings.environment})")
    yield  # Server runs here. Anything after yield runs at shutdown.
    print("👋 Shutting down")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: lets the React frontend (different port) call this API.
# Without this, the browser blocks the request as cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes live under /api/. Health check becomes /api/health.
app.include_router(routes_health.router, prefix="/api")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "NBA Win Probability Engine — see /docs for API"}