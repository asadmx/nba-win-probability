"""Health check endpoint.

Every production backend needs one of these. Used by:
- Docker (to know if the container started successfully)
- Load balancers (to know if they should route traffic here)
- Render/Vercel (to verify deployment worked)
- You, during development, to verify the server is alive
"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "nba-win-probability-backend"}