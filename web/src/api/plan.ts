import { apiGet, apiPost } from "./client";
import type { ItineraryDay, PlanSession } from "./client";

export interface TierCut {
  kind: string;
  label: string;
  save: number;
  explain: string;
}

export interface BudgetTier {
  tier: string;
  label: string;
  low: number;
  high: number;
  fit: "under" | "within" | "over";
  cuts: TierCut[];
}

export interface BudgetTiers {
  session_id: string;
  days: number;
  people: number;
  current_total: number;
  tiers: BudgetTier[];
  gap: { to_economy: number | null; to_comfort: number | null };
}

export interface DayProfile {
  day: number;
  date: string;
  walk_km: number;
  climb_m: number;
  elevator_ok: boolean;
  intensity: "low" | "mid" | "high";
  tips: string[];
}

export type EnrichedPlanSession = PlanSession & {
  day_profile: DayProfile[];
  generation_error?: string | null;
};

export async function startPlanAsync(
  userData: Record<string, unknown>,
): Promise<{ session_id: string; stage: number }> {
  return apiPost<{ session_id: string; stage: number }>("/api/plan/async", { user_data: userData });
}

export async function fetchBudgetTiers(sessionId: string): Promise<BudgetTiers> {
  return apiGet<BudgetTiers>(`/api/budget/tiers?session_id=${encodeURIComponent(sessionId)}`);
}

export async function fetchPlanEnriched(sessionId: string): Promise<EnrichedPlanSession> {
  const res = await apiGet<{ state: EnrichedPlanSession }>(`/api/plan/${encodeURIComponent(sessionId)}`);
  return res.state;
}

export async function replanWeather(
  sessionId: string,
  weatherByDay: Record<string, unknown>,
): Promise<{ itinerary: ItineraryDay[]; notes: string[]; state: EnrichedPlanSession }> {
  return apiPost<{ itinerary: ItineraryDay[]; notes: string[]; state: EnrichedPlanSession }>(
    `/api/plan/${encodeURIComponent(sessionId)}/replan-weather`,
    { weather_by_day: weatherByDay },
  );
}