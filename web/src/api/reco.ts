import { apiGet } from "./client";

export interface RecoResult {
  target: string;
  kind: "attraction" | "city";
  keyword: string;
  search_url: string;
  blurb: string;
  provider: "ai" | "local";
}

export async function fetchAttractionReco(name: string): Promise<RecoResult> {
  return apiGet<RecoResult>(`/api/attractions/${encodeURIComponent(name)}/xiaohongshu`);
}

export async function fetchCityReco(name: string): Promise<RecoResult> {
  return apiGet<RecoResult>(`/api/cities/${encodeURIComponent(name)}/xiaohongshu`);
}