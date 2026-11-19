export interface ThemeColor {
  from: string;
  to: string;
}

export const FALLBACK_THEMES: ThemeColor[] = [
  { from: "#7a5cff", to: "#c77dff" },
  { from: "#00b8a9", to: "#90e0ef" },
  { from: "#ff4d2e", to: "#ffb703" },
  { from: "#ff477e", to: "#ffd6e0" },
  { from: "#3a86ff", to: "#4cc9f0" },
  { from: "#06d6a0", to: "#d8f3dc" },
];

export const CITY_THEME: Record<string, ThemeColor> = {
  北京: { from: "#e63946", to: "#ff8a5b" },
  上海: { from: "#3a86ff", to: "#00c2ff" },
  广州: { from: "#ff6b00", to: "#ffb703" },
  深圳: { from: "#00b4d8", to: "#7a5cff" },
  成都: { from: "#ff477e", to: "#ff85a1" },
  杭州: { from: "#06d6a0", to: "#00b4d8" },
  西安: { from: "#b5179e", to: "#ff4d6d" },
  三亚: { from: "#00c2ff", to: "#06d6a0" },
  厦门: { from: "#ff8fab", to: "#ffb703" },
  青岛: { from: "#0096c7", to: "#48cae4" },
  丽江: { from: "#ff7b00", to: "#ffd000" },
  大理: { from: "#00b894", to: "#7bed9f" },
  昆明: { from: "#ff4d6d", to: "#ffb703" },
  哈尔滨: { from: "#4361ee", to: "#4cc9f0" },
  重庆: { from: "#e63946", to: "#ff7b00" },
  武汉: { from: "#ff8500", to: "#ffd000" },
  南京: { from: "#7a5cff", to: "#c77dff" },
  苏州: { from: "#06d6a0", to: "#ffd166" },
  桂林: { from: "#00b4d8", to: "#90e0ef" },
  长沙: { from: "#ff2d75", to: "#ff9e00" },
};

export function cityTheme(name: string): ThemeColor {
  const key = (name ?? "").trim();
  if (!key) return FALLBACK_THEMES[0];
  const hit = CITY_THEME[key];
  if (hit) return hit;
  let sum = 0;
  for (let i = 0; i < key.length; i += 1) sum += key.charCodeAt(i);
  return FALLBACK_THEMES[sum % FALLBACK_THEMES.length];
}

export const TAG_EMOJI: Record<string, string> = {
  人文古迹: "🏯",
  自然风光: "🏞️",
  网红打卡: "📸",
  购物: "🛍️",
  美食文化: "🍜",
  主题乐园: "🎡",
};

export function tagEmoji(tag: string): string {
  return TAG_EMOJI[tag] ?? "✨";
}

export function cityInitial(name: string): string {
  const trimmed = (name ?? "").trim();
  return trimmed ? Array.from(trimmed)[0] : "云";
}

const OPEN_RANGE = /^(\d{2}):(\d{2})-(\d{2}):(\d{2})/;

export function openState(
  openTime: string,
  now: Date = new Date(),
): { state: "open" | "closed" | "always" | "unknown"; label: string } {
  const text = (openTime ?? "").trim();
  if (!text) return { state: "unknown", label: openTime };

  if (text.includes("全天")) return { state: "always", label: "全天开放" };

  if (text.includes("闭馆") && now.getDay() === 1) return { state: "closed", label: "周一闭馆" };

  const match = OPEN_RANGE.exec(text);
  if (match) {
    const start = Number(match[1]) * 60 + Number(match[2]);
    const end = Number(match[3]) * 60 + Number(match[4]);
    const current = now.getHours() * 60 + now.getMinutes();
    const open = start <= end ? current >= start && current <= end : current >= start || current <= end;
    return open ? { state: "open", label: "当前开放" } : { state: "closed", label: "当前停闭" };
  }

  return { state: "unknown", label: openTime };
}