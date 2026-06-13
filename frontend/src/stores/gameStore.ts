import { create } from "zustand";
import type { GameSummary, LiveGame, WSTick } from "../types";

export type ConnectionStatus = "idle" | "connecting" | "connected" | "ended" | "error";

interface GameState {
  selectedGameId: number | null;
  selectedGame: GameSummary | null;
  liveGameId: string | null;
  connectionStatus: ConnectionStatus;
  isPaused: boolean;
  ticks: WSTick[];
  currentScore: { home: number; away: number };
  currentPeriod: number;
  currentClock: number;
  currentProbability: number;

  selectGame: (game: GameSummary) => void;
  selectLiveGame: (game: LiveGame) => void;
  resetTicks: () => void;
  appendTick: (tick: WSTick) => void;
  setStatus: (s: ConnectionStatus) => void;
  setIsPaused: (v: boolean) => void;
}

const RESET = {
  ticks: [] as WSTick[],
  isPaused: false,
  currentScore: { home: 0, away: 0 },
  currentPeriod: 1,
  currentClock: 720,
  currentProbability: 0.5,
  connectionStatus: "connecting" as ConnectionStatus,
};

export const useGameStore = create<GameState>((set) => ({
  selectedGameId: null,
  selectedGame: null,
  liveGameId: null,
  connectionStatus: "idle",
  isPaused: false,
  ticks: [],
  currentScore: { home: 0, away: 0 },
  currentPeriod: 1,
  currentClock: 720,
  currentProbability: 0.5,

  selectGame: (game) =>
    set({ selectedGameId: game.game_id, selectedGame: game, liveGameId: null, ...RESET }),

  selectLiveGame: (game) =>
    set({ liveGameId: game.game_id, selectedGameId: null, selectedGame: null, ...RESET }),

  resetTicks: () => set({ ticks: [], currentScore: { home: 0, away: 0 }, currentPeriod: 1, currentClock: 720, currentProbability: 0.5 }),

  appendTick: (tick) =>
    set((s) => ({
      ticks: [...s.ticks, tick],
      currentScore: { home: tick.play.score_home, away: tick.play.score_away },
      currentPeriod: tick.play.period,
      currentClock: tick.play.clock_seconds,
      currentProbability: tick.home_win_prob,
    })),

  setStatus: (s) => set({ connectionStatus: s }),
  setIsPaused: (v) => set({ isPaused: v }),
}));