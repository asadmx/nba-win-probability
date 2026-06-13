import { useEffect, useState } from "react";
import { getTodayGames } from "../lib/api";
import type { LiveGame } from "../types";

interface Props {
  onSelectLive: (game: LiveGame) => void;
  selectedGameId: string | null;
}

function StatusBadge({ status, text }: { status: number; text: string }) {
  if (status === 2) {
    return (
      <span className="flex items-center gap-1.5 text-prob-win font-mono text-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-prob-win animate-pulse" />
        {text}
      </span>
    );
  }
  if (status === 3) {
    return <span className="font-mono text-xs text-text-secondary">Final</span>;
  }
  return <span className="font-mono text-xs text-text-secondary">{text}</span>;
}

export function LivePicker({ onSelectLive, selectedGameId }: Props) {
  const [games, setGames] = useState<LiveGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gameDate, setGameDate] = useState("");

  useEffect(() => {
    let cancelled = false;
    const fetchGames = () => {
      getTodayGames()
        .then((res) => {
          if (cancelled) return;
          setGames(res.games);
          setGameDate(res.game_date);
          setLoading(false);
        })
        .catch((e) => {
          if (cancelled) return;
          setError(String(e));
          setLoading(false);
        });
    };

    fetchGames();
    // Refresh every 30 seconds to catch status changes.
    const interval = setInterval(fetchGames, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return (
      <div className="px-6 py-4 font-mono text-xs text-text-secondary">
        loading today's games…
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-6 py-4 font-mono text-xs text-prob-loss">
        {error}
      </div>
    );
  }

  if (games.length === 0) {
    return (
      <div className="px-6 py-4 font-mono text-xs text-text-secondary">
        no games scheduled today
      </div>
    );
  }

  return (
    <div>
      <div className="px-6 py-2 bg-[#0B0D12] border-b border-[#1F2230] font-mono text-xs text-text-secondary tracking-wider">
        {gameDate} · {games.length} games
      </div>
      {games.map((g) => {
        const isSelected = g.game_id === selectedGameId;
        const isLive = g.game_status === 2;

        return (
          <button
            key={g.game_id}
            onClick={() => isLive && onSelectLive(g)}
            disabled={!isLive}
            className={`w-full text-left px-6 py-3 border-b border-[#1F2230] transition-colors ${
              isLive
                ? "hover:bg-[#15171F] cursor-pointer"
                : "opacity-50 cursor-not-allowed"
            } ${isSelected ? "bg-[#15171F]" : ""}`}
          >
            <div className="flex items-center justify-between mb-1">
              <StatusBadge status={g.game_status} text={g.game_status_text} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span>
                <span className="font-bold">{g.away_team_abbr}</span>
                <span className="text-text-secondary mx-1">@</span>
                <span className="font-bold">{g.home_team_abbr}</span>
              </span>
              {g.game_status >= 2 && (
                <span className="font-mono text-xs tabular-nums text-text-secondary">
                  {g.away_pts}-{g.home_pts}
                </span>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}