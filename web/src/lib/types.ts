// Veri şeması: docs/ARCHITECTURE.md ile birebir aynı alan adları.

export type SourceStatus = 'ok' | 'partial' | 'missing' | 'skipped';

export interface Source {
  id: string;
  name: string;
  status: SourceStatus;
  fetched_at: string | null;
  note?: string | null;
  items?: number;
}

export interface League {
  id: string;
  name: string;
  country: string;
  priority: number;
}

export type MarketKey =
  | '1' | 'X' | '2' | '1X' | 'X2' | '12'
  | 'O1.5' | 'U1.5' | 'O2.5' | 'U2.5' | 'O3.5' | 'U3.5'
  | 'BTTS_Y' | 'BTTS_N';

export type HtFtKey = '1/1' | '1/X' | '1/2' | 'X/1' | 'X/X' | 'X/2' | '2/1' | '2/X' | '2/2';

export type FormLetter = 'W' | 'D' | 'L';

export interface TeamStats {
  form: FormLetter[];
  venue_form: FormLetter[];
  gf_avg: number | null;
  ga_avg: number | null;
  venue_gf_avg: number | null;
  venue_ga_avg: number | null;
  xg_avg: number | null;
  xga_avg: number | null;
  btts_pct: number | null;
  o25_pct: number | null;
  clean_sheets_venue: number | null;
  venue_n: number | null;
  corners_avg: number | null;
  cards_avg: number | null;
  n: number | null;
}

export interface H2H {
  date: string;
  home: string;
  away: string;
  score: string;
}

export interface MissingPlayer {
  name: string;
  reason: 'sakat' | 'cezalı' | 'şüpheli' | string;
  key: boolean;
}

export interface SquadSide {
  missing: MissingPlayer[];
  rotation_risk: boolean;
  coach_change: boolean;
  adjustment?: number | null;
}

export interface ConsensusSource {
  source: string;
  picks: Record<string, string>;
  probs?: Partial<Record<MarketKey, number>> | null;
  fetched_at?: string | null;
}

export interface ConsensusSummary {
  market: string;
  agree: number;
  total: number;
  text: string;
}

export interface ValueItem {
  market: string;
  model_p: number;
  implied_p: number;
  odds: number;
  edge: number;
  ev: number;
}

export interface Pick {
  market: string;
  label: string;
  p: number;
  odds: number | null;
  stars: number;
  is_value: boolean;
}

export type Odds = Partial<Record<MarketKey, number>> & Record<string, number | undefined>;

export type OddsSnapshot = Partial<Record<MarketKey, number>> & { t: string };

/** 50 örnek maç akışı — yalnızca gösterim; olasılıklar 10.000 simülasyondan gelir. */
export interface SampleGoal {
  min: number | string;          // 23 veya "45+2" / "90+3"
  side: 'home' | 'away';
}

export interface SampleRun {
  i: number;
  ft: [number, number];
  ht: [number, number];
  goals: SampleGoal[];
}

export interface SampleRuns {
  n: number;
  runs: SampleRun[];
  summary: { '1': number; X: number; '2': number; 'O2.5': number; BTTS_Y: number; top_scores: [string, number][] };
  note: string;
}

export interface Model {
  lambda_home: number;
  lambda_away: number;
  sims: number;
  rho: number;
  probs: Partial<Record<MarketKey, number>>;
  htft: Partial<Record<HtFtKey, number>>;
  top_scores: { score: string; p: number }[];
  score_matrix: number[][];
  total_goals: number[];
  data_quality: 'high' | 'medium' | 'low';
  notes: string[];
  sample_runs?: SampleRuns;
  /** Ek gol marketleri (İY, handikap, gol aralığı, takım golü, kombine...) — anahtarlar day.market_labels'ta */
  extra?: Record<string, number>;
  corners?: CountPrediction;
  cards?: CountPrediction;
}

export interface CountPrediction {
  exp_home: number;
  exp_away: number;
  exp_total: number;
  league_avg: number;
  dispersion: number;
  probs: Record<string, number>;
  referee?: string | null;
  referee_factor?: number | null;
  referee_matches?: number;
}

export interface MarketCategory { id: string; title: string; keys: string[] }

export interface OddsAnalysis {
  status: 'ok' | 'dusuk_guven' | 'az_ornek';
  n: number;
  scope?: 'lig' | 'tüm ligler';
  match_point?: { '1': number; X: number; '2': number };
  markets?: { market: string; observed: number; ci: [number, number]; market_p: number | null; diff: number | null; notable: boolean }[];
  disclaimer: string;
}

export type NewsTag = 'sakat' | 'ceza' | 'td' | 'kadro' | 'transfer';

export interface NewsItem {
  title: string;
  url: string;
  source: string;
  published: string;
  tags: (NewsTag | string)[];
}

export interface MatchNews {
  home: NewsItem[];
  away: NewsItem[];
  fetched_at: string | null;
}

export interface Match {
  id: string;
  code: string | null;
  mbs: number | null;
  league: string;
  league_name: string;
  league_priority: number;
  kickoff: string;
  home: { name: string };
  away: { name: string };
  status: 'scheduled' | 'live' | 'finished';
  result: { ft: [number, number]; ht: [number, number] | null } | null;
  odds: Odds | null;
  odds_history: OddsSnapshot[] | null;
  market: {
    implied: Partial<Record<MarketKey, number>>;
    margin: Record<string, number>;
    movement: Partial<Record<MarketKey, number>>;
    drop_alarms: MarketKey[];
  } | null;
  model: Model | null;
  stats: { home: TeamStats; away: TeamStats; h2h: H2H[] } | null;
  news?: MatchNews | null;
  squad: { home: SquadSide | null; away: SquadSide | null; source: string | null; fetched_at: string | null } | null;
  consensus: { sources: ConsensusSource[]; summary: ConsensusSummary[] } | null;
  value: ValueItem[];
  value_note?: string | null;
  pick: Pick | null;
  comment: string | null;
  comment_source: 'kural' | 'llm' | null;
  flags: string[];
  provenance: Record<string, { source: string; t: string }> | null;
  odds_analysis?: OddsAnalysis | null;
}

export interface DayFile {
  schema_version: number;
  date: string;
  generated_at: string;
  run_label: string;
  sources: Source[];
  leagues: League[];
  matches: Match[];
  market_labels?: Record<string, string>;
  market_categories?: MarketCategory[];
}

export interface IndexFile {
  dates: string[];
  latest: string;
}

export interface ScoreBlock {
  n: number;
  hit_rate: number | null;
  brier_1x2: number | null;
  roi: number | null;
  staked: number;
  profit: number;
}

export interface Scorecard {
  generated_at: string;
  overall: ScoreBlock;
  last30: ScoreBlock;
  by_league: { league: string; name: string; n: number; hit_rate: number | null; roi: number | null }[];
  by_market: { market: string; label: string; n: number; hit_rate: number | null; roi: number | null; trust: number }[];
  calibration: { bin: string; predicted: number; observed: number; n: number }[];
  bankroll: { date: string; balance: number }[];
  recent: { date: string; match: string; pick: string; odds: number | null; won: boolean; score: string }[];
}

export type HealthLevel = 'ok' | 'uyari' | 'alarm' | 'kronik' | 'kapali';
export interface SourceHealth {
  history: ('ok' | 'partial' | 'missing' | 'skipped')[];
  streak: number;
  ok_rate: number | null;
  last_ok: string | null;
  level: HealthLevel;
}
export interface QualityReport {
  matches: number;
  league_mapped_pct: number | null;
  team_match_pct: number | null;
  odds_coverage_pct: number | null;
  model_coverage_pct: number | null;
  cross_source_match_pct: number | null;
  cross_source?: { pct: number | null; joined?: number; nesine?: number; iddaa?: number; note?: string };
  unmatched_teams: Record<string, string[]>;
  unknown_leagues: string[];
  validation: Record<string, number>;
}
export type StatusFile =
  | {
      generated_at?: string;
      sources: Source[];
      health?: { sources: Record<string, SourceHealth>; alerts: string[]; runs: number };
      quality?: QualityReport;
    }
  | Source[];

export interface BacktestSummary {
  n: number;
  model_brier: number | null;
  market_brier: number | null;
  model_logloss: number | null;
  market_logloss: number | null;
  roi_value_bets: number | null;
  n_value_bets: number;
}

/** backtest.json içindeki eşik taraması satırı (alpha = model/piyasa karışım ağırlığı) */
export interface BacktestGridRow {
  alpha: number;
  edge: number;
  bets: number;
  profit?: number | null;
  roi: number | null;
}

export interface Backtest {
  generated_at: string;
  seasons: string[];
  leagues: string[];
  method?: string;
  summary: BacktestSummary;
  by_league: (BacktestSummary & { league: string; name?: string; blend_brier?: Record<string, number>; grid?: BacktestGridRow[] })[];
  /** Opsiyonel: alpha × edge taraması (pipeline üretiyorsa) */
  grid?: BacktestGridRow[];
  /** Opsiyonel: alpha → karışım Brier skoru */
  blend_brier?: Record<string, number>;
}
