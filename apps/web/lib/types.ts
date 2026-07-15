/** Shared API types — mirror the FastAPI backend contract (spec §7). */

export interface Author {
  name: string;
}

export interface Paper {
  arxiv_id: string;
  title: string;
  abstract: string;
  authors: Author[];
  categories: string[];
  primary_category: string;
  published_at: string;
  pdf_url: string | null;
  citation_count: number | null;
}

export type RecallSource = "vector" | "graph" | "fresh" | "explore";

export interface FeedItem {
  impression_id: string;
  position: number;
  recall_source: RecallSource;
  reason: string;
  paper: Paper;
}

export interface FeedResponse {
  request_id: string;
  items: FeedItem[];
}

export type EventType =
  | "visible"
  | "click_abstract"
  | "click_pdf"
  | "save"
  | "dismiss"
  | "dwell";

export interface FeedbackEvent {
  impression_id: string;
  event_type: EventType;
  /** dwell only: milliseconds. Omitted for all other event types. */
  value?: number;
}

export interface SavedItem {
  saved_at: string;
  paper: Paper;
}

export interface SavedResponse {
  items: SavedItem[];
}

export interface DailyMetric {
  day: string;
  impressions: number;
  clicks: number;
  saves: number;
  dismisses: number;
  ctr: number;
  profile_drift: number | null;
  model_version: string;
}

export interface ModelInfo {
  version: string;
  model_type: string;
  status: string;
  created_at: string;
  metrics: Record<string, number> | null;
}

export interface StatsResponse {
  daily: DailyMetric[];
  models: {
    production: ModelInfo | null;
    staging: ModelInfo | null;
  };
  profile: {
    interaction_count: number;
    updated_at: string | null;
  };
}
