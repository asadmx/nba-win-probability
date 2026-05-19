import { useEffect, useRef } from "react";
import { useGameStore } from "../stores/gameStore";

function formatClock(seconds: number): string {
  if (seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function periodLabel(period: number): string {
  return period <= 4 ? `Q${period}` : `OT${period - 4}`;
}

/**
 * Reverse-chronological feed of plays. Most recent at the top.
 * Auto-scrolls to keep newest play visible.
 */
export function PlayFeed() {
  const ticks = useGameStore((s) => s.ticks);
  const containerRef = useRef<HTMLDivElement>(null);

  // We display newest at top, so a "newer" tick means scroll to top.
  useEffect(() => {
    containerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [ticks.length]);

  // Reverse so newest is rendered first (top).
  const displayed = [...ticks].reverse().slice(0, 100);

  return (
    <div className="border border-[#1F2230] bg-[#15171F] flex flex-col h-full">
      <div className="font-mono text-xs text-text-secondary tracking-wider px-6 py-3 border-b border-[#1F2230]">
        PLAY-BY-PLAY · {ticks.length} EVENTS
      </div>
      <div ref={containerRef} className="overflow-y-auto flex-1">
        {displayed.length === 0 ? (
          <div className="px-6 py-4 text-text-secondary font-mono text-sm">
            waiting for first play…
          </div>
        ) : (
          displayed.map((t, idx) => {
            const probPct = (t.home_win_prob * 100).toFixed(1);
            return (
              <div
                key={t.play.action_number}
                className={`px-6 py-3 border-b border-[#1F2230] flex items-start gap-4 ${
                  idx === 0 ? "bg-[#1A1D26]" : ""
                }`}
              >
                <div className="font-mono text-xs text-text-secondary tabular-nums shrink-0 w-16">
                  {periodLabel(t.play.period)} {formatClock(t.play.clock_seconds)}
                </div>
                <div className="font-mono text-xs tabular-nums shrink-0 w-16">
                  {t.play.score_home}-{t.play.score_away}
                </div>
                <div className="text-sm flex-1 leading-snug">
                  {t.play.description ?? t.play.action_type}
                </div>
                <div className="font-mono text-xs tabular-nums shrink-0 w-14 text-right text-text-secondary">
                  {probPct}%
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}