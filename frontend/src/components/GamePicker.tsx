import { useEffect, useMemo, useState } from "react";
import { listGames } from "../lib/api";
import { LivePicker } from "./LivePicker";
import { useGameStore } from "../stores/gameStore";
import type { GameSummary, LiveGame } from "../types";

const SEASONS = ["2025-26", "2024-25", "2023-24"];

const TEAMS = {
  East: ["ATL","BOS","BKN","CHA","CHI","CLE","DET","IND","MIA","MIL","NYK","ORL","PHI","TOR","WAS"],
  West: ["DAL","DEN","GSW","HOU","LAC","LAL","MEM","MIN","NOP","OKC","PHX","POR","SAC","SAS","UTA"],
} as const;

type Stage = "team" | "games";
type Tab = "live" | "historical";

function groupByMonth(games: GameSummary[]) {
  const groups = new Map<string, GameSummary[]>();
  for (const g of games) {
    const month = (g.game_date ?? "unknown").slice(0, 7);
    if (!groups.has(month)) groups.set(month, []);
    groups.get(month)!.push(g);
  }
  return Array.from(groups.entries())
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([label, games]) => ({ label, games }));
}

function monthLabel(yyyyMm: string) {
  if (yyyyMm === "unknown") return "Unknown";
  const [y, m] = yyyyMm.split("-");
  const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${names[parseInt(m, 10) - 1]} ${y}`;
}

export function GamePicker() {
  const [tab, setTab] = useState<Tab>("live");
  const [season, setSeason] = useState("2025-26");
  const [stage, setStage] = useState<Stage>("team");
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [games, setGames] = useState<GameSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedGameId = useGameStore((s) => s.selectedGameId);
  const liveGameId = useGameStore((s) => s.liveGameId);
  const selectGame = useGameStore((s) => s.selectGame);
  const selectLiveGame = useGameStore((s) => s.selectLiveGame);

  useEffect(() => {
    if (tab !== "historical") return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    listGames(season, 2000)
      .then((res) => { if (!cancelled) setGames(res.games); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [season, tab]);

  useEffect(() => {
    setStage("team");
    setSelectedTeam(null);
  }, [season]);

  const teamGames = useMemo(() => {
    if (!selectedTeam) return [];
    return games.filter(
      (g) => g.home_team_abbr === selectedTeam || g.away_team_abbr === selectedTeam,
    );
  }, [games, selectedTeam]);

  return (
    <div className="border-r border-[#1F2230] bg-[#0F1117] w-72 flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-[#1F2230]">
        {(["live", "historical"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-3 font-mono text-xs tracking-wider transition-colors ${
              tab === t
                ? "text-text-primary border-b-2 border-prob-win"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {t === "live" ? "● LIVE" : "HISTORY"}
          </button>
        ))}
      </div>

      {/* Live tab */}
      {tab === "live" && (
        <div className="overflow-y-auto flex-1">
          <LivePicker
            onSelectLive={(g: LiveGame) => selectLiveGame(g)}
            selectedGameId={liveGameId}
          />
        </div>
      )}

      {/* Historical tab */}
      {tab === "historical" && (
        <>
          <div className="px-6 py-4 border-b border-[#1F2230]">
            <div className="font-mono text-xs text-text-secondary tracking-wider mb-2">SEASON</div>
            <div className="flex gap-2 flex-wrap">
              {SEASONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setSeason(s)}
                  className={`px-3 py-1 font-mono text-xs border ${
                    season === s
                      ? "border-prob-win text-prob-win"
                      : "border-[#2A2E3D] text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {stage === "games" && (
            <button
              onClick={() => { setStage("team"); setSelectedTeam(null); }}
              className="px-6 py-3 border-b border-[#1F2230] hover:bg-[#15171F] text-left font-mono text-xs text-text-secondary tracking-wider"
            >
              ← TEAMS
            </button>
          )}

          <div className="overflow-y-auto flex-1">
            {loading && <div className="px-6 py-4 font-mono text-xs text-text-secondary">loading…</div>}
            {error && <div className="px-6 py-4 font-mono text-xs text-prob-loss">{error}</div>}

            {!loading && !error && stage === "team" && (
              <div>
                {(["East", "West"] as const).map((conf) => (
                  <div key={conf}>
                    <div className="px-6 py-2 bg-[#0B0D12] border-b border-[#1F2230] font-mono text-xs text-text-secondary tracking-wider">
                      {conf.toUpperCase()}
                    </div>
                    <div className="grid grid-cols-3 gap-0">
                      {TEAMS[conf].map((t) => (
                        <button
                          key={t}
                          onClick={() => { setSelectedTeam(t); setStage("games"); }}
                          className="px-3 py-4 border-b border-r border-[#1F2230] hover:bg-[#15171F] font-mono text-sm tracking-wider transition-colors"
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {!loading && !error && stage === "games" && (
              <div>
                <div className="px-6 py-3 bg-[#0B0D12] border-b border-[#1F2230]">
                  <div className="font-mono text-lg font-bold tracking-wider">{selectedTeam}</div>
                  <div className="font-mono text-xs text-text-secondary">{teamGames.length} games · {season}</div>
                </div>
                {teamGames.map((g) => {
                  const isSelected = g.game_id === selectedGameId;
                  const isHome = g.home_team_abbr === selectedTeam;
                  const opponent = isHome ? g.away_team_abbr : g.home_team_abbr;
                  const teamScore = isHome ? g.home_pts : g.away_pts;
                  const oppScore = isHome ? g.away_pts : g.home_pts;
                  const won = teamScore > oppScore;
                  return (
                    <button
                      key={g.game_id}
                      onClick={() => selectGame(g)}
                      className={`w-full text-left px-6 py-3 border-b border-[#1F2230] hover:bg-[#15171F] transition-colors ${isSelected ? "bg-[#15171F]" : ""}`}
                    >
                      <div className="font-mono text-xs text-text-secondary mb-1">{g.game_date ?? "—"}</div>
                      <div className="flex items-center justify-between text-sm">
                        <span>
                          <span className="text-text-secondary text-xs mr-1">{isHome ? "vs" : "@"}</span>
                          <span className="font-bold">{opponent}</span>
                        </span>
                        <span className="font-mono text-xs tabular-nums">
                          <span className={won ? "text-prob-win" : "text-prob-loss"}>{won ? "W" : "L"}</span>
                          <span className="text-text-secondary ml-2">{teamScore}-{oppScore}</span>
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}