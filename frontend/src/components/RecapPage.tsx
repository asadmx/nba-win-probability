import { useEffect, useState } from "react";
import { getSeasonRecap } from "../lib/api";
import { useGameStore } from "../stores/gameStore";
import type { RecapGame, RecapResponse } from "../types";

function periodLabel(period: number): string {
  return period <= 4 ? `Q${period}` : `OT${period - 4}`;
}

function formatClock(seconds: number): string {
  if (seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function GameRow({ game, metric, metricLabel }: { game: RecapGame; metric: number; metricLabel: string }) {
  const setRecapGameId = useGameStore((s) => s.setRecapTarget);

  return (
    <button
      onClick={() => setRecapGameId(game.game_id)}
      className="w-full text-left px-6 py-4 border-b border-[#1F2230] hover:bg-[#15171F] transition-colors flex items-center gap-4"
    >
      <div className="font-mono text-xl font-bold text-prob-win tabular-nums w-28 shrink-0 text-right">
        {metric.toFixed(1)}%
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-xs text-text-secondary mb-1">
          {game.game_date} · {metricLabel}
        </div>
        <div className="text-sm font-bold mb-1">
          {game.away_team_abbr} {game.away_pts} @ {game.home_team_abbr} {game.home_pts}
        </div>
        <div className="text-sm text-text-secondary leading-snug">
          {periodLabel(game.swing_play.period)} {formatClock(game.swing_play.clock_seconds)} —{" "}
          {game.swing_play.description}
        </div>
      </div>
    </button>
  );
}

export function RecapPage({ season }: { season: string }) {
  const [data, setData] = useState<RecapResponse | null>(null);
  const [tab, setTab] = useState<"swings" | "volatile">("swings");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getSeasonRecap(season)
      .then((res) => { if (!cancelled) setData(res); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [season]);

  if (loading) {
    return <div className="flex-1 flex items-center justify-center font-mono text-text-secondary">loading recap…</div>;
  }
  if (error || !data) {
    return <div className="flex-1 flex items-center justify-center font-mono text-prob-loss">{error ?? "no data"}</div>;
  }

  const games = tab === "swings" ? data.biggest_swings : data.most_volatile;

  return (
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
      <div className="px-8 py-6 border-b border-[#1F2230]">
        <div className="font-mono text-xs text-text-secondary tracking-wider mb-2">
          NBA · WIN PROBABILITY ENGINE
        </div>
        <h1 className="text-3xl font-bold mb-1">{season} Season Recap</h1>
        <p className="text-text-secondary text-sm">
          Every game run through the model — ranked by the biggest mid-game probability swings and the most volatile games overall.
        </p>
      </div>

      <div className="flex border-b border-[#1F2230]">
        <button
          onClick={() => setTab("swings")}
          className={`px-6 py-3 font-mono text-xs tracking-wider transition-colors ${
            tab === "swings" ? "text-text-primary border-b-2 border-prob-win" : "text-text-secondary hover:text-text-primary"
          }`}
        >
          BIGGEST SWINGS
        </button>
        <button
          onClick={() => setTab("volatile")}
          className={`px-6 py-3 font-mono text-xs tracking-wider transition-colors ${
            tab === "volatile" ? "text-text-primary border-b-2 border-prob-win" : "text-text-secondary hover:text-text-primary"
          }`}
        >
          MOST VOLATILE
        </button>
      </div>

      <div className="overflow-y-auto flex-1">
        {games.map((g) => (
          <GameRow
            key={g.game_id}
            game={g}
            metric={tab === "swings" ? g.biggest_swing_pct : g.volatility_score}
            metricLabel={tab === "swings" ? "biggest swing" : `volatility · ${g.n_big_swings} swings ≥2%`}
          />
        ))}
      </div>
    </div>
  );
}