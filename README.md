# Live NBA Win Probability Engine

Real-time win probability predictions for NBA games, powered by a PyTorch neural
network trained on 10 seasons of play-by-play data. Built end-to-end: data
pipeline, ML training, FastAPI backend with WebSocket streaming, and a React +
TypeScript dashboard.

## Status

🚧 In active development. See [ROADMAP.md](./ROADMAP.md) for the build plan.

## Stack

**Backend:** Python 3.11, FastAPI, PyTorch, scikit-learn, SQLAlchemy, WebSockets
**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Recharts, Zustand
**Infra:** Docker, GitHub Actions, Render (backend), Vercel (frontend)

## Quick Start

Requires Docker Desktop.

```bash
docker compose up --build
```
- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system design.