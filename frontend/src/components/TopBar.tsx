import { useGameStore } from "../stores/gameStore";

function formatClock(seconds: number): string {
  if (seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function periodLabel(period: number): string {
  if (period <= 4) return `Q${period}`;
  return `OT${period - 4}`;
}

export function TopBar() {
  const game = useGameStore((s) => s.selectedGame);
  const score = useGameStore((s) => s.currentScore);
  const period = useGameStore((s) => s.currentPeriod);
  const clock = useGameStore((s) => s.currentClock);
  const status = useGameStore((s) => s.connectionStatus);

  if (!game) {
    return (
      <div className="border-b border-[#1F2230] px-8 py-4 text-text-secondary font-mono text-xs">
        no game selected
      </div>
    );
  }

  const liveDotColor =
    status === "connected" ? "bg-prob-win" :
    status === "connecting" ? "bg-prob-neutral" :
    status === "ended" ? "bg-text-secondary" :
    "bg-prob-loss";

  const liveLabel =
    status === "connected" ? "LIVE" :
    status === "connecting" ? "CONNECTING" :
    status === "ended" ? "ENDED" :
    "ERROR";

  return (
    <div className="border-b border-[#1F2230] px-8 py-4 flex items-center gap-8">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${liveDotColor} ${status === "connected" ? "animate-pulse" : ""}`} />
        <span className="font-mono text-xs text-text-secondary tracking-wider">{liveLabel}</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right">
          <div className="font-mono text-xs text-text-secondary">AWAY</div>
          <div className="text-2xl font-bold tracking-tight">{game.away_team_abbr}</div>
        </div>
        <div className="font-mono text-4xl tabular-nums">
          {score.away} <span className="text-text-secondary mx-2">·</span> {score.home}
        </div>
        <div>
          <div className="font-mono text-xs text-text-secondary">HOME</div>
          <div className="text-2xl font-bold tracking-tight">{game.home_team_abbr}</div>
        </div>
      </div>

      <div className="ml-auto font-mono text-sm text-text-secondary">
        <span className="text-text-primary">{periodLabel(period)}</span>
        <span className="mx-3">·</span>
        <span className="tabular-nums">{formatClock(clock)}</span>
      </div>
    </div>
  );
}