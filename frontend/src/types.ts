export interface Delta {
  move: string;
  jfrog_equivalent: string;
  strategic_impact: "high" | "medium" | "low";
  talking_points: string[];
}
export interface Article {
  id: number; title: string; url: string; source_name: string; source_type: string;
  published_at: string | null; fetched_at: string | null; competitors: string[];
  domain: string | null; event_type: string | null; summary: string | null;
  jfrog_impact: number | null; so_what: string | null; delta: Delta | null;
}
export interface ArticleRef {
  id: number; title: string; url: string; published_at: string | null; source_name: string;
}
export interface Claim { text: string; article_ids: number[]; kind?: "threat" | "opportunity" }
export interface Digest {
  date: string; exec_summary: string; generated_at: string; model_used: string;
  sections: {
    top_developments: Claim[];
    by_competitor: { competitor: string; highlights: Claim[] }[];
    threats_opportunities: Claim[];
  };
  articles: Record<string, ArticleRef>;
}
export interface Competitor {
  slug: string; name: string; color: string; article_count: number;
  high_impact_count: number; last_activity: string | null;
}
export interface Battlecard {
  slug: string; name: string; color: string;
  base: { strengths: string[]; weaknesses: string[]; how_jfrog_wins: string[] };
  recent_moves: Claim[]; generated_at: string | null; articles: Record<string, ArticleRef>;
}
export interface MatrixCell { level: "full" | "partial" | "addon" | "none"; note: string }
export interface Matrix {
  vendors: string[]; vendor_labels: Record<string, string>;
  rows: { capability: string; values: Record<string, MatrixCell> }[];
}
export interface Meta {
  provider: string; model: string; demo_mode: boolean; refresh_hour: number;
  last_refresh: string | null; competitors: number; version: string;
  refresh_state: { running: boolean; stage: string; errors: string[] };
}
export interface SourceHealth {
  source_name: string; ok: boolean; items_found: number; error: string | null; started_at: string;
}
export interface ArticlePage { items: Article[]; total: number; page: number; page_size: number }
