import { useEffect, useState } from "react";
import { GamePicker } from "./components/GamePicker";
import { TopBar } from "./components/TopBar";
import { ProbabilityGauge } from "./components/ProbabilityGauge";
import { ProbabilityChart } from "./components/ProbabilityChart";
import { PlayFeed } from "./components/PlayFeed";
import { SimControls } from "./components/SimControls";
import { KeyMoments } from "./components/KeyMoments";
import { RecapPage } from "./components/RecapPage";
import { TriviaPage } from "./components/TriviaPage";
import { useGameSocket } from "./hooks/useGameSocket";
import { useGameStore } from "./stores/gameStore";
import { listGames } from "./lib/api";

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center px-8">
      <div className="font-mono text-xs text-text-secondary tracking-wider mb-3">
        NBA · WIN PROBABILITY ENGINE
      </div>
      <h1 className="text-4xl font-bold mb-4 max-w-xl">
        Pick a game to start.
      </h1>
      <p className="text-text-secondary max-w-md leading-relaxed">
        Select a live game from the LIVE tab, browse historical games in HISTORY,
        or check out the SEASON RECAP for the year's most dramatic moments.
      </p>
    </div>
  );
}

function Dashboard() {
  useGameSocket(10);

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <TopBar />
      <SimControls />
      <div className="flex-1 grid grid-cols-2 gap-6 p-6 overflow-hidden">
        <div className="flex flex-col gap-6 min-h-0 overflow-y-auto">
          <ProbabilityGauge />
          <ProbabilityChart />
          <KeyMoments />
        </div>
        <div className="min-h-0">
          <PlayFeed />
        </div>
      </div>
    </div>
  );
}

type View = "dashboard" | "recap" | "trivia";

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const selectedGameId = useGameStore((s) => s.selectedGameId);
  const liveGameId = useGameStore((s) => s.liveGameId);
  const recapTarget = useGameStore((s) => s.recapTarget);
  const selectGame = useGameStore((s) => s.selectGame);
  const setRecapTarget = useGameStore((s) => s.setRecapTarget);
  const hasGame = selectedGameId != null || liveGameId != null;

  useEffect(() => {
    if (recapTarget == null) return;
    listGames("2025-26", 2000).then((res) => {
      const game = res.games.find((g) => g.game_id === recapTarget);
      if (game) {
        selectGame(game);
        setView("dashboard");
      }
      setRecapTarget(null);
    });
  }, [recapTarget, selectGame, setRecapTarget]);

  return (
    <div className="h-screen w-screen flex flex-col bg-bg-base text-text-primary">
      <div className="flex border-b border-[#1F2230] shrink-0">
        {(["dashboard", "recap", "trivia"] as View[]).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-6 py-2 font-mono text-xs tracking-wider transition-colors ${
              view === v
                ? "text-text-primary border-b-2 border-prob-win"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {v === "dashboard" ? "DASHBOARD" : v === "recap" ? "SEASON RECAP" : "TRIVIA"}
          </button>
        ))}
      </div>

      <div className="flex-1 flex min-h-0">
        {view === "dashboard" ? (
          <>
            <GamePicker />
            {hasGame ? <Dashboard /> : <EmptyState />}
          </>
        ) : view === "recap" ? (
          <RecapPage season="2025-26" />
        ) : (
          <TriviaPage />
        )}
      </div>
    </div>
  );
}