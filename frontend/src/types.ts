export interface GameSummary {
  game_id: number;
  season: string;
  game_date: string | null;
  home_team_abbr: string;
  away_team_abbr: string;
  home_pts: number;
  away_pts: number;
  home_won: boolean;
}

export interface GamesListResponse {
  games: GameSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface PlaySummary {
  action_number: number;
  period: number;
  clock_seconds: number;
  seconds_remaining: number;
  score_home: number;
  score_away: number;
  score_margin: number;
  action_type: string;
  description: string | null;
}

export interface WSConnected {
  type: "connected";
  game_id: number;
  game_meta: {
    home_team_abbr: string;
    away_team_abbr: string;
    home_team_id: number;
    away_team_id: number;
    game_date: string | null;
    final_score: { home: number; away: number };
  };
}

export interface WSTick {
  type: "tick";
  play: {
    action_number: number;
    period: number;
    clock_seconds: number;
    seconds_remaining: number;
    action_type: string;
    description: string | null;
    score_home: number;
    score_away: number;
  };
  state: {
    score_margin: number;
    home_has_possession: boolean;
    home_fouls_period: number;
    away_fouls_period: number;
    home_in_bonus: boolean;
    away_in_bonus: boolean;
    momentum_5: number;
    recent_scoring_run: number;
  };
  home_win_prob: number;
  model_version: string;
}

export interface WSGameEnd {
  type: "game_end";
  final_score: { home: number; away: number };
  home_won: boolean;
}

export interface WSError {
  type: "error";
  message: string;
}

export interface WSPaused { type: "paused"; }
export interface WSResumed { type: "resumed"; }
export interface WSSpeedSet { type: "speed_set"; speed: number; }

export type WSMessage = WSConnected | WSTick | WSGameEnd | WSError | WSPaused | WSResumed | WSSpeedSet;

export interface LiveGame {
  game_id: string;
  home_team_abbr: string;
  away_team_abbr: string;
  home_team_id: number;
  away_team_id: number;
  home_pts: number;
  away_pts: number;
  game_status: number;       // 1=scheduled, 2=live, 3=final
  game_status_text: string;
  period: number;
  game_clock: string;
}

export interface TodayResponse {
  games: LiveGame[];
  game_date: string;
}

export interface RecapSwingPlay {
  period: number;
  clock_seconds: number;
  description: string | null;
  score_home: number;
  score_away: number;
}

export interface RecapGame {
  game_id: number;
  game_date: string;
  home_team_abbr: string;
  away_team_abbr: string;
  home_pts: number;
  away_pts: number;
  home_won: boolean;
  biggest_swing_pct: number;
  swing_play: RecapSwingPlay;
  prob_after_swing: number;
  volatility_score: number;
  n_big_swings: number;
}

export interface RecapResponse {
  season: string;
  biggest_swings: RecapGame[];
  most_volatile: RecapGame[];
}