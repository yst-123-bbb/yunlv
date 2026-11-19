const baseUrl = import.meta.env.VITE_API_BASE ?? "";

export interface ItineraryItem {
  name: string;
  start?: string;
  end?: string;
  lng?: number | null;
  lat?: number | null;
  indoor?: boolean;
}

export interface ItineraryDay {
  day: number;
  date: string;
  items: ItineraryItem[];
}

export interface BudgetBreakdown {
  transport?: number;
  hotel?: number;
  tickets?: number;
  food?: number;
  city_transport?: number;
  shopping?: number;
  reserve?: number;
  grand_total?: number;
  per_person?: number;
}

export interface PlanSession {
  session_id: string;
  stage: number;
  user_data: Record<string, unknown>;
  transport: Record<string, unknown> | null;
  plans: Record<string, unknown>[];
  chosen_plan: Record<string, unknown> | null;
  itinerary: ItineraryDay[];
  budget: BudgetBreakdown | null;
  history: Record<string, unknown>[];
}

export interface Issue {
  code?: string;
  message?: string;
  day?: number;
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function readDetail(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (data.detail !== undefined) return JSON.stringify(data.detail);
  } catch {
    // 响应体不是 JSON，退回到状态码描述
  }
  return res.statusText || `http_${res.status}`;
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    throw new ApiError(0, `网络请求失败: ${err instanceof Error ? err.message : String(err)}`);
  }

  if (!res.ok) throw new ApiError(res.status, await readDetail(res));
  if (res.status === 204) return undefined as T;

  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError(res.status, "响应不是合法 JSON");
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>("GET", path);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>("POST", path, body);
}