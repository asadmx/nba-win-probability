import { useMemo } from "react";
import { useGameStore } from "../stores/gameStore";
import type { WSTick } from "../types";

interface Moment {
  tick: WSTick;
  prevProb: number;
  swing: number;
  absSwing: number;
}

function periodLabel(period: number): string {
  return period <= 4 ? `Q${period}` : `OT${period - 4}`;
}

function formatClock(seconds: number): string {
  if (seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function KeyMoments() {
  const ticks = useGameStore((s) => s.ticks);
  const game = useGameStore((s) => s.selectedGame);
  const status = useGameStore((s) => s.connectionStatus);

  const moments = useMemo<Moment[]>(() => {
    if (ticks.length < 2) return [];
    const swings: Moment[] = [];
    for (let i = 1; i < ticks.length; i++) {
      const prev = ticks[i - 1];
      const curr = ticks[i];
      const swing = curr.home_win_prob - prev.home_win_prob;
      const absSwing = Math.abs(swing);
      if (absSwing >= 0.02) {
        swings.push({ tick: curr, prevProb: prev.home_win_prob, swing, absSwing });
      }
    }
    return swings.sort((a, b) => b.absSwing - a.absSwing).slice(0, 5);
  }, [ticks]);

  if (moments.length === 0) return null;
  if (status !== "connected" && status !== "ended") return null;

  return (
    <div className="border border-[#1F2230] bg-[#15171F]">
      <div className="px-6 py-3 border-b border-[#1F2230] font-mono text-xs text-text-secondary tracking-wider">
        KEY MOMENTS · TOP {moments.length} SWINGS
      </div>
      <div>
        {moments.map((m, idx) => {
          const homeGained = m.swing > 0;
          const swingPct = (m.absSwing * 100).toFixed(1);
          const beneficiary = homeGained
            ? (game?.home_team_abbr ?? "HOME")
            : (game?.away_team_abbr ?? "AWAY");
          // The beneficiary always *gained* probability — always green/up.
          const color = "text-prob-win";
          const arrow = "▲";
          const desc = m.tick.play.description ?? m.tick.play.action_type;

          return (
            <div
              key={idx}
              className="px-6 py-3 border-b border-[#1F2230] flex items-start gap-4 last:border-0"
            >
              <div className="font-mono text-xs text-text-secondary shrink-0 w-16">
                {periodLabel(m.tick.play.period)} {formatClock(m.tick.play.clock_seconds)}
              </div>
              <div className="font-mono text-xs tabular-nums shrink-0 w-20 text-text-secondary">
                <div>{game?.away_team_abbr ?? "AWAY"} {m.tick.play.score_away}</div>
                <div>{game?.home_team_abbr ?? "HOME"} {m.tick.play.score_home}</div>
              </div>
              <div className="text-sm flex-1 leading-snug text-text-primary">
                {desc}
              </div>
              <div className={`font-mono text-xs tabular-nums shrink-0 text-right ${color}`}>
                <div className="font-bold">{beneficiary}</div>
                <div>{arrow} {swingPct}%</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}