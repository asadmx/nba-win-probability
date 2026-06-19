"""Trivia generation endpoint — calls Google Gemini API server-side.

POST /api/trivia/generate
  Body: {"difficulty": "easy"|"medium"|"hard"}
  Returns: {"questions": [...]}
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Explicitly load backend/.env since this module reads os.environ directly.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

router = APIRouter(prefix="/trivia", tags=["trivia"])

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DIFFICULTY_PROMPTS = {
    "easy": "easy — basic NBA facts, famous players, team nicknames, obvious records",
    "medium": "medium — statistics, playoff history, draft picks, team records, memorable moments",
    "hard": "hard — obscure records, specific game scores, trade details, advanced statistics, deep NBA history",
}

QUESTION_RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "type": {
                "type": "STRING",
                "enum": ["multiple_choice", "true_false", "guess_player"],
            },
            "question": {"type": "STRING"},
            "options": {"type": "ARRAY", "items": {"type": "STRING"}},
            "answer": {"type": "STRING"},
            "explanation": {"type": "STRING"},
            "difficulty": {"type": "STRING"},
        },
        "required": ["type", "question", "options", "answer", "explanation", "difficulty"],
    },
}


class TriviaRequest(BaseModel):
    difficulty: str = "medium"


@router.post("/generate")
async def generate_trivia(req: TriviaRequest) -> dict:
    if req.difficulty not in DIFFICULTY_PROMPTS:
        raise HTTPException(status_code=400, detail="difficulty must be easy, medium, or hard")

    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured")

    diff_prompt = DIFFICULTY_PROMPTS[req.difficulty]

    prompt = f"""Generate exactly 10 NBA trivia questions at {diff_prompt} difficulty.

Mix of formats:
- 5 multiple_choice questions (4 options each)
- 3 guess_player questions (give stats/clues, 4 player name options)
- 2 true_false questions (options are exactly ["True", "False"])

Cover a mix of: current players, historical players, team history, championships, records, draft history, famous moments.

Make sure "answer" exactly matches one of the "options" strings exactly. Make questions fun and interesting."""

    last_error: str = "unknown error"
    data = None

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    GEMINI_API_URL,
                    headers={
                        "x-goog-api-key": GEMINI_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": 6000,
                            "temperature": 0.9,
                            "responseMimeType": "application/json",
                            "responseSchema": QUESTION_RESPONSE_SCHEMA,
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            break  # success
        except httpx.HTTPStatusError as e:
            last_error = f"{e.response.status_code} — {e.response.text}"
            if e.response.status_code in (503, 429) and attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            raise HTTPException(status_code=503, detail=f"Gemini API error: {last_error}")
        except httpx.HTTPError as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            raise HTTPException(status_code=503, detail=f"Gemini API error after 3 attempts: {last_error}")

    if data is None:
        raise HTTPException(status_code=503, detail=f"Gemini API error after retries: {last_error}")

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise HTTPException(status_code=500, detail=f"Unexpected Gemini response shape: {data}")

    clean = re.sub(r"```json\s*|\s*```", "", text).strip()

    try:
        questions = json.loads(clean)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse Gemini response: {e}")

    if not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(status_code=500, detail="Invalid question format from Gemini")

    return {"questions": questions}