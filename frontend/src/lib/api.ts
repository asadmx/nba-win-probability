import type { GameSummary, GamesListResponse, TodayResponse } from "../types";
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new ApiError(`${res.status} ${res.statusText}`, res.status);
  }
  return res.json() as Promise<T>;
}

export async function listGames(
  season?: string,
  limit = 100,
  offset = 0,
): Promise<GamesListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (season) params.set("season", season);
  return get<GamesListResponse>(`/api/games?${params}`);
}

export async function getGame(gameId: number): Promise<GameSummary> {
  // Note: backend returns GameDetail (game + plays). We only use the game part here.
  const detail = await get<{ game: GameSummary }>(`/api/games/${gameId}`);
  return detail.game;
}

// Used to build the WS URL — same host, different protocol.
export function wsUrlForGame(gameId: number, speed = 10): string {
  // Replace http(s):// with ws(s)://
  const wsBase = API_BASE.replace(/^http/, "ws");
  return `${wsBase}/ws/game/${gameId}?speed=${speed}`;
}

export async function getTodayGames(): Promise<TodayResponse> {
  return get<TodayResponse>("/api/live/today");
}

export function wsUrlForLiveGame(gameId: string): string {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return `${wsBase}/ws/live/${gameId}`;
}