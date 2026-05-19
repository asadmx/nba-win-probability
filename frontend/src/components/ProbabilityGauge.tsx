import { useGameStore } from "../stores/gameStore";

/**
 * Big probability display. Two halves: home above 50%, away below.
 * The dominant side gets a colored bar; the loser side gets a thin grey one.
 */
export function ProbabilityGauge() {
  const prob = useGameStore((s) => s.currentProbability);
  const game = useGameStore((s) => s.selectedGame);

  const homeFavored = prob >= 0.5;
  const dominantPct = homeFavored ? prob : 1 - prob;
  const dominantTeam = homeFavored ? game?.home_team_abbr : game?.away_team_abbr;

  const homePct = (prob * 100).toFixed(1);
  const awayPct = ((1 - prob) * 100).toFixed(1);

  const dominantColor =
    dominantPct >= 0.85 ? "text-prob-win" :
    dominantPct >= 0.6 ? "text-prob-win" :
    "text-prob-neutral";

  return (
    <div className="p-8 border border-[#1F2230] bg-[#15171F]">
      <div className="font-mono text-xs text-text-secondary tracking-wider mb-2">
        WIN PROBABILITY
      </div>

      <div className="flex items-baseline gap-3 mb-6">
        <div className={`text-6xl font-bold tabular-nums ${dominantColor}`}>
          {(dominantPct * 100).toFixed(1)}%
        </div>
        <div className="font-mono text-sm text-text-secondary">
          {dominantTeam ?? "—"}
        </div>
      </div>

      {/* Horizontal bar split between teams */}
      <div className="h-2 bg-[#0B0D12] flex overflow-hidden">
        <div
          className="bg-prob-win transition-all duration-500"
          style={{ width: `${prob * 100}%` }}
        />
        <div
          className="bg-prob-loss transition-all duration-500"
          style={{ width: `${(1 - prob) * 100}%` }}
        />
      </div>

      <div className="flex justify-between mt-2 font-mono text-xs text-text-secondary">
        <span>{game?.home_team_abbr ?? "HOME"} {homePct}%</span>
        <span>{awayPct}% {game?.away_team_abbr ?? "AWAY"}</span>
      </div>
    </div>
  );
}