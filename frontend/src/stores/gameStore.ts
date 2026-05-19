import { create } from "zustand";
import type { GameSummary, WSTick } from "../types";

export type ConnectionStatus = "idle" | "connecting" | "connected" | "ended" | "error";

interface GameState {
  selectedGameId: number | null;
  selectedGame: GameSummary | null;
  connectionStatus: ConnectionStatus;

  // Ticks accumulate as the simulator streams. We keep them in chronological
  // order for the chart and play feed.
  ticks: WSTick[];

  // Convenience accessors derived from the latest tick.
  currentScore: { home: number; away: number };
  currentPeriod: number;
  currentClock: number; // seconds remaining in period
  currentProbability: number;

  // Actions
  selectGame: (game: GameSummary) => void;
  resetTicks: () => void;
  appendTick: (tick: WSTick) => void;
  setStatus: (s: ConnectionStatus) => void;
}

export const useGameStore = create<GameState>((set) => ({
  selectedGameId: null,
  selectedGame: null,
  connectionStatus: "idle",
  ticks: [],
  currentScore: { home: 0, away: 0 },
  currentPeriod: 1,
  currentClock: 720,
  currentProbability: 0.5,

  selectGame: (game) =>
    set({
      selectedGameId: game.game_id,
      selectedGame: game,
      ticks: [],
      currentScore: { home: 0, away: 0 },
      currentPeriod: 1,
      currentClock: 720,
      currentProbability: 0.5,
      connectionStatus: "connecting",
    }),

  resetTicks: () =>
    set({
      ticks: [],
      currentScore: { home: 0, away: 0 },
      currentPeriod: 1,
      currentClock: 720,
      currentProbability: 0.5,
    }),

  appendTick: (tick) =>
    set((s) => ({
      ticks: [...s.ticks, tick],
      currentScore: { home: tick.play.score_home, away: tick.play.score_away },
      currentPeriod: tick.play.period,
      currentClock: tick.play.clock_seconds,
      currentProbability: tick.home_win_prob,
    })),

  setStatus: (s) => set({ connectionStatus: s }),
}));