export const TASTE_OPTIONS: { value: string; label: string }[] = [
  { value: "local", label: "当地特色" },
  { value: "spicy", label: "嗜辣" },
  { value: "light", label: "清淡" },
  { value: "sweet", label: "甜口" },
  { value: "seafood", label: "海鲜" },
  { value: "hotpot", label: "火锅" },
  { value: "bbq", label: "烧烤" },
  { value: "noodles", label: "面食" },
  { value: "veggie", label: "素食" },
  { value: "drinks", label: "饮品甜点" },
];

export interface Prefs {
  address?: string;
  tastes: string[];
  travel_style: "fast" | "slow";
  accommodation_budget?: number;
  transport_budget?: number;
  total_budget?: number;
  attraction_pref: string[];
  onboarded?: boolean;
}

export interface Favorite {
  sessionId: string;
  title: string;
  cities: string[];
  days: number;
  grandTotal: number;
  savedAt: string;
}

export interface TodoSpot {
  name: string;
  city: string;
  image?: string;
  ticket_price: number;
  addedAt: string;
}

const PREFS_KEY = "yunlv.prefs";
const FAVORITES_KEY = "yunlv.favorites";
const SEARCH_HISTORY_KEY = "yunlv.searchHistory";
const ONBOARDED_KEY = "yunlv.onboarded";
const TODOS_KEY = "yunlv.todos";
const SEARCH_HISTORY_LIMIT = 10;

function defaultPrefs(): Prefs {
  return { tastes: [], travel_style: "slow", attraction_pref: [] };
}

function safeParse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function safeRead(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** 写入失败（隐私模式 / 配额）时静默忽略，读侧仍能拿到默认值。 */
function safeWrite(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 存储不可用时不影响页面渲染
  }
}

function safeRemove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // 存储不可用时不影响页面渲染
  }
}

function normalizePrefs(value: unknown): Prefs {
  const base = defaultPrefs();
  if (!value || typeof value !== "object") return base;
  const raw = value as Partial<Prefs>;
  return {
    ...base,
    ...raw,
    tastes: Array.isArray(raw.tastes) ? raw.tastes.filter((t): t is string => typeof t === "string") : [],
    attraction_pref: Array.isArray(raw.attraction_pref)
      ? raw.attraction_pref.filter((t): t is string => typeof t === "string")
      : [],
    travel_style: raw.travel_style === "fast" ? "fast" : "slow",
  };
}

function normalizeFavorites(value: unknown): Favorite[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is Favorite =>
      !!item &&
      typeof item === "object" &&
      typeof (item as Favorite).sessionId === "string" &&
      (item as Favorite).sessionId.length > 0,
  );
}

function normalizeHistory(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((q): q is string => typeof q === "string" && q.length > 0).slice(0, SEARCH_HISTORY_LIMIT);
}

export function readPrefs(): Prefs {
  const parsed = safeParse<unknown>(safeRead(PREFS_KEY));
  if (parsed === null) {
    const fallback = defaultPrefs();
    safeWrite(PREFS_KEY, JSON.stringify(fallback));
    const onboarded = safeRead(ONBOARDED_KEY);
    return onboarded === null ? fallback : { ...fallback, onboarded: onboarded === "true" };
  }

  const prefs = normalizePrefs(parsed);
  const onboarded = safeRead(ONBOARDED_KEY);
  if (onboarded !== null) prefs.onboarded = onboarded === "true";
  return prefs;
}

export function writePrefs(patch: Partial<Prefs>): Prefs {
  const merged: Prefs = { ...readPrefs(), ...patch };
  if (typeof merged.onboarded === "boolean") {
    safeWrite(ONBOARDED_KEY, merged.onboarded ? "true" : "false");
  }
  safeWrite(PREFS_KEY, JSON.stringify(merged));
  return merged;
}

export function readFavorites(): Favorite[] {
  const parsed = safeParse<unknown>(safeRead(FAVORITES_KEY));
  if (parsed === null) {
    safeWrite(FAVORITES_KEY, JSON.stringify([]));
    return [];
  }
  return normalizeFavorites(parsed);
}

export function isFavorite(sessionId: string): boolean {
  return readFavorites().some((item) => item.sessionId === sessionId);
}

export function toggleFavorite(item: Favorite): boolean {
  const favorites = readFavorites();
  const exists = favorites.some((fav) => fav.sessionId === item.sessionId);
  const next = exists
    ? favorites.filter((fav) => fav.sessionId !== item.sessionId)
    : [item, ...favorites];
  safeWrite(FAVORITES_KEY, JSON.stringify(next));
  return !exists;
}

export function removeFavorite(sessionId: string): void {
  const next = readFavorites().filter((fav) => fav.sessionId !== sessionId);
  safeWrite(FAVORITES_KEY, JSON.stringify(next));
}

export function readSearchHistory(): string[] {
  const parsed = safeParse<unknown>(safeRead(SEARCH_HISTORY_KEY));
  if (parsed === null) {
    safeWrite(SEARCH_HISTORY_KEY, JSON.stringify([]));
    return [];
  }
  return normalizeHistory(parsed);
}

export function pushSearchHistory(q: string): string[] {
  const keyword = q.trim();
  if (!keyword) return readSearchHistory();

  const next = [keyword, ...readSearchHistory().filter((item) => item !== keyword)].slice(
    0,
    SEARCH_HISTORY_LIMIT,
  );
  safeWrite(SEARCH_HISTORY_KEY, JSON.stringify(next));
  return next;
}

export function clearSearchHistory(): void {
  safeRemove(SEARCH_HISTORY_KEY);
}
function normalizeTodos(value: unknown): TodoSpot[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is TodoSpot =>
      !!item && typeof item === "object" && typeof (item as TodoSpot).name === "string" && (item as TodoSpot).name.length > 0,
  );
}

export function readTodos(): TodoSpot[] {
  const parsed = safeParse<unknown>(safeRead(TODOS_KEY));
  if (parsed === null) {
    safeWrite(TODOS_KEY, JSON.stringify([]));
    return [];
  }
  return normalizeTodos(parsed);
}

export function isTodo(name: string): boolean {
  return readTodos().some((item) => item.name === name);
}

export function toggleTodo(item: TodoSpot): boolean {
  const todos = readTodos();
  const exists = todos.some((entry) => entry.name === item.name);
  const next = exists ? todos.filter((entry) => entry.name !== item.name) : [item, ...todos];
  safeWrite(TODOS_KEY, JSON.stringify(next));
  return !exists;
}

export function removeTodo(name: string): void {
  safeWrite(
    TODOS_KEY,
    JSON.stringify(readTodos().filter((entry) => entry.name !== name)),
  );
}