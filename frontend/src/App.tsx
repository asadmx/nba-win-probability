import { GamePicker } from "./components/GamePicker";
import { TopBar } from "./components/TopBar";
import { ProbabilityGauge } from "./components/ProbabilityGauge";
import { ProbabilityChart } from "./components/ProbabilityChart";
import { PlayFeed } from "./components/PlayFeed";
import { SimControls } from "./components/SimControls";
import { useGameSocket } from "./hooks/useGameSocket";
import { useGameStore } from "./stores/gameStore";

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
        Select a live game from the LIVE tab, or browse historical games in HISTORY.
        The PyTorch model updates P(home wins) after every play.
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
        <div className="flex flex-col gap-6 min-h-0">
          <ProbabilityGauge />
          <ProbabilityChart />
        </div>
        <div className="min-h-0">
          <PlayFeed />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const selectedGameId = useGameStore((s) => s.selectedGameId);
  const liveGameId = useGameStore((s) => s.liveGameId);
  const hasGame = selectedGameId != null || liveGameId != null;

  return (
    <div className="h-screen w-screen flex flex-col bg-bg-base text-text-primary">
      <div className="flex-1 flex min-h-0">
        <GamePicker />
        {hasGame ? <Dashboard /> : <EmptyState />}
      </div>
    </div>
  );
}