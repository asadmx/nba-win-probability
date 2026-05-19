import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useGameStore } from "../stores/gameStore";

/**
 * Renders the entire probability arc of the game so far.
 *
 * X-axis: total game time elapsed in minutes (0 to ~48, more for OT)
 * Y-axis: P(home wins), 0 to 100%
 *
 * The area fills green above 50% (home favored) and red below.
 */
export function ProbabilityChart() {
  const ticks = useGameStore((s) => s.ticks);

  // Transform raw ticks into chart-friendly data points.
  // We compute "minutes elapsed" so the X axis advances naturally.
  // Regulation period length: 12 minutes. OT: 5 minutes.
  const data = useMemo(() => {
    return ticks.map((t) => {
      const periodSeconds = t.play.period <= 4 ? 720 : 300;
      const periodLengthMin = t.play.period <= 4 ? 12 : 5;
      const completedPeriodsMin =
        t.play.period <= 4
          ? (t.play.period - 1) * 12
          : 48 + (t.play.period - 5) * 5;
      const minutesElapsed = completedPeriodsMin + (periodSeconds - t.play.clock_seconds) / 60;
      return {
        minutes: Number(minutesElapsed.toFixed(2)),
        prob: t.home_win_prob * 100,
        score: `${t.play.score_home}-${t.play.score_away}`,
      };
    });
  }, [ticks]);

  return (
    <div className="p-6 border border-[#1F2230] bg-[#15171F] h-80">
      <div className="font-mono text-xs text-text-secondary tracking-wider mb-4">
        WIN PROBABILITY OVER TIME
      </div>
      <ResponsiveContainer width="100%" height="85%">
        <AreaChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
          <defs>
            <linearGradient id="probGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22C55E" stopOpacity={0.4} />
              <stop offset="50%" stopColor="#22C55E" stopOpacity={0.05} />
              <stop offset="50%" stopColor="#EF4444" stopOpacity={0.05} />
              <stop offset="100%" stopColor="#EF4444" stopOpacity={0.4} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#1F2230" vertical={false} />
          <XAxis
            dataKey="minutes"
            type="number"
            domain={[0, "dataMax"]}
            tick={{ fill: "#7A7F8E", fontFamily: "JetBrains Mono", fontSize: 11 }}
            tickFormatter={(v) => `${Math.round(v)}'`}
            stroke="#2A2E3D"
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            tick={{ fill: "#7A7F8E", fontFamily: "JetBrains Mono", fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
            stroke="#2A2E3D"
          />
          <ReferenceLine y={50} stroke="#2A2E3D" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0B0D12",
              border: "1px solid #2A2E3D",
              fontFamily: "JetBrains Mono",
              fontSize: 12,
            }}
            labelStyle={{ color: "#7A7F8E" }}
            labelFormatter={(v) => `t = ${Number(v).toFixed(1)} min`}
            formatter={(value: number, _name, payload) => [
              `${value.toFixed(1)}%`,
              `P(home) · ${payload.payload.score}`,
            ]}
          />
          <Area
            type="monotone"
            dataKey="prob"
            stroke="#E8EAF0"
            strokeWidth={2}
            fill="url(#probGradient)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}