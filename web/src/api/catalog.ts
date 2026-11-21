import { apiGet, apiPost } from "./client";

export interface CityBrief {
  name: string;
  province: string;
  tag: string;
  spots: string[];
  attraction_count?: number;
}

export interface Attraction {
  name: string;
  city: string;
  address: string;
  ticket_price: number;
  open_time: string;
  tags: string[];
  features: string;
  tips: string;
  indoor: boolean;
  likes: number;
  image?: string;
  image_fallback?: string;
  image_meta?: { source_url?: string; author?: string; license?: string };
}

export interface Comment {
  id: string;
  target: string;
  target_type: string;
  author: string;
  text: string;
  likes: number;
  source_url: string;
  source: string;
  fetched_at: string;
}

export interface ChatDraft {
  departure: string;
  destination: string;
  days: number;
  people: number;
  dep_date: string;
  tastes?: string[];
  attraction_prefs?: string[];
  transport_pref?: string;
  hotel_level?: string;
  budget?: number;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface SearchPayload {
  cities: CityBrief[];
  attractions: Attraction[];
}

export async function fetchCities(): Promise<CityBrief[]> {
  const data = await apiGet<{ items: CityBrief[] }>("/api/cities");
  return data.items;
}

export async function fetchCity(name: string): Promise<{ city: CityBrief; attractions: Attraction[] }> {
  return apiGet<{ city: CityBrief; attractions: Attraction[] }>(`/api/cities/${encodeURIComponent(name)}`);
}

export async function fetchAttractions(params: { city?: string; limit?: number }): Promise<Attraction[]> {
  const query = new URLSearchParams();
  if (params.city) query.set("city", params.city);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  const data = await apiGet<{ items: Attraction[] }>(`/api/attractions${qs ? `?${qs}` : ""}`);
  return data.items;
}

export async function fetchAttraction(name: string): Promise<Attraction> {
  const data = await apiGet<{ attraction: Attraction }>(`/api/attractions/${encodeURIComponent(name)}`);
  return data.attraction;
}

export async function searchAll(q: string): Promise<{ cities: CityBrief[]; attractions: Attraction[] }> {
  return apiGet<SearchPayload>(`/api/search?q=${encodeURIComponent(q)}`);
}

/** 调用方负责 300ms 防抖与竞态处理；空关键词不发请求。 */
export async function suggestPlaces(q: string): Promise<{ cities: CityBrief[]; attractions: Attraction[] }> {
  if (!q.trim()) return { cities: [], attractions: [] };
  return searchAll(q);
}

export async function fetchTemplateNames(): Promise<string[]> {
  const data = await apiGet<{ items: string[] }>("/api/templates");
  return data.items;
}

export async function fetchTemplate(name: string): Promise<Record<string, unknown>> {
  const data = await apiGet<{ state: Record<string, unknown> }>(`/api/templates/${encodeURIComponent(name)}`);
  return data.state;
}

export async function fetchHot(): Promise<{ cities: CityBrief[]; attractions: Attraction[] }> {
  return apiGet<SearchPayload>("/api/search/hot");
}

export async function fetchComments(target: string, limit?: number): Promise<Comment[]> {
  const query = new URLSearchParams({ target });
  if (limit !== undefined) query.set("limit", String(limit));
  const data = await apiGet<{ items: Comment[] }>(`/api/comments?${query.toString()}`);
  return data.items;
}

export async function sendChat(
  messages: ChatMessage[],
  prefs?: Record<string, unknown> | null,
): Promise<{ reply: string; draft: ChatDraft | null; provider: string }> {
  return apiPost<{ reply: string; draft: ChatDraft | null; provider: string }>("/api/chat", {
    messages,
    prefs: prefs ?? null,
  });
}