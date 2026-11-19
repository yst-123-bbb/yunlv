import { useCallback, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  TASTE_OPTIONS,
  readFavorites,
  readPrefs,
  readTodos,
  removeFavorite,
  removeTodo,
  writePrefs,
} from "../storage/localStore";
import type { Favorite, Prefs, TodoSpot } from "../storage/localStore";
import { cityInitial, cityTheme } from "../theme/palette";
import EmptyState from "../components/EmptyState";
import PlaceImage from "../components/PlaceImage";
import Toast from "../components/Toast";

const STYLE_OPTIONS: { value: Prefs["travel_style"]; label: string }[] = [
  { value: "slow", label: "慢节奏" },
  { value: "fast", label: "快节奏" },
];

const ATTRACTION_PREF_OPTIONS: { value: string; label: string }[] = [
  { value: "nature", label: "自然风光" },
  { value: "culture", label: "历史人文" },
  { value: "family", label: "亲子科普" },
  { value: "photo", label: "拍照打卡" },
  { value: "night", label: "夜游体验" },
  { value: "museum", label: "博物馆" },
  { value: "park", label: "主题乐园" },
  { value: "hotspring", label: "温泉度假" },
];

function toInputValue(value?: number): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "";
}

function toNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

function toggleIn(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

export default function MePage() {
  const [prefs] = useState<Prefs>(() => readPrefs());
  const [address, setAddress] = useState(prefs.address ?? "");
  const [tastes, setTastes] = useState<string[]>(prefs.tastes);
  const [travelStyle, setTravelStyle] = useState<Prefs["travel_style"]>(prefs.travel_style);
  const [accommodationBudget, setAccommodationBudget] = useState(toInputValue(prefs.accommodation_budget));
  const [transportBudget, setTransportBudget] = useState(toInputValue(prefs.transport_budget));
  const [totalBudget, setTotalBudget] = useState(toInputValue(prefs.total_budget));
  const [attractionPref, setAttractionPref] = useState<string[]>(prefs.attraction_pref);

  const [toast, setToast] = useState("");
  const closeToast = useCallback(() => setToast(""), []);

  const [todos, setTodos] = useState<TodoSpot[]>(() => readTodos());
  const [favorites, setFavorites] = useState<Favorite[]>(() => readFavorites());

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    writePrefs({
      address: address.trim(),
      tastes,
      travel_style: travelStyle,
      accommodation_budget: toNumber(accommodationBudget),
      transport_budget: toNumber(transportBudget),
      total_budget: toNumber(totalBudget),
      attraction_pref: attractionPref,
    });
    setToast("偏好已保存");
  }

  function handleRemoveFavorite(sessionId: string) {
    removeFavorite(sessionId);
    setFavorites(readFavorites());
  }

  function handleRemoveTodo(name: string) {
    removeTodo(name);
    setTodos(readTodos());
  }

  return (
    <div>
      <header className="pageHeader">
        <h2>我的</h2>
      </header>

      <section className="card">
        <h2 className="cardTitle">出行偏好</h2>
        <form className="prefForm" onSubmit={handleSubmit}>
          <label className="field">
            <span>常住地 / 出发地址</span>
            <input
              type="text"
              value={address}
              placeholder="例如：杭州西湖区"
              onChange={(event) => setAddress(event.target.value)}
            />
          </label>

          <div className="field">
            <span>口味</span>
            <div className="chipRow">
              {TASTE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={tastes.includes(option.value) ? "chip chipActive" : "chip"}
                  aria-pressed={tastes.includes(option.value)}
                  onClick={() => setTastes((prev) => toggleIn(prev, option.value))}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span>节奏</span>
            <div className="chipRow">
              {STYLE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={travelStyle === option.value ? "chip chipActive" : "chip"}
                  aria-pressed={travelStyle === option.value}
                  onClick={() => setTravelStyle(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="formGrid">
            <label className="field">
              <span>住宿预算（元）</span>
              <input
                type="number"
                min="0"
                value={accommodationBudget}
                onChange={(event) => setAccommodationBudget(event.target.value)}
              />
            </label>
            <label className="field">
              <span>交通预算（元）</span>
              <input
                type="number"
                min="0"
                value={transportBudget}
                onChange={(event) => setTransportBudget(event.target.value)}
              />
            </label>
            <label className="field">
              <span>总预算（元）</span>
              <input
                type="number"
                min="0"
                value={totalBudget}
                onChange={(event) => setTotalBudget(event.target.value)}
              />
            </label>
          </div>

          <div className="field">
            <span>景点偏好</span>
            <div className="chipRow">
              {ATTRACTION_PREF_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={attractionPref.includes(option.value) ? "chip chipActive" : "chip"}
                  aria-pressed={attractionPref.includes(option.value)}
                  onClick={() => setAttractionPref((prev) => toggleIn(prev, option.value))}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="chipRow">
            <button className="btn btnPrimary" type="submit">
              保存偏好
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2 className="sectionTitle">想去清单</h2>
        {todos.length === 0 ? (
          <EmptyState
            emoji="⭐"
            title="还没有想去的景点"
            hint="在景点详情页点「加入想去」，就能在这里统一查看。"
          />
        ) : (
          <div className="todoList">
            {todos.map((item) => (
              <article key={item.name} className="placeCard">
                <PlaceImage src={item.image} name={item.name} city={item.city} />
                <Link className="placeCardTitle" to={`/attraction/${encodeURIComponent(item.name)}`}>
                  {item.name}
                </Link>
                <span className="placeCardMeta">
                  {item.city} · 门票 {item.ticket_price > 0 ? `${Math.round(item.ticket_price)} 元` : "免费"}
                </span>
                <button
                  className="btn btnGhost"
                  type="button"
                  onClick={() => handleRemoveTodo(item.name)}
                  aria-label={`从想去清单移除 ${item.name}`}
                >
                  移除
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="sectionTitle">我的收藏</h2>
        {favorites.length === 0 ? (
          <EmptyState
            emoji="🧡"
            title="还没有收藏的行程"
            hint="去行程详情页点收藏，之后可以在这里快速找回。"
          />
        ) : (
          <div className="todoList">
            {favorites.map((item) => {
              const primaryCity = item.cities[0] ?? "";
              const theme = cityTheme(primaryCity);
              return (
                <article key={item.sessionId} className="cityCard">
                  <span
                    className="cityBadge"
                    style={{ background: `linear-gradient(135deg, ${theme.from}, ${theme.to})` }}
                  >
                    {cityInitial(primaryCity || item.title)}
                  </span>
                  <div>
                    <Link
                      className="placeCardTitle"
                      to={`/plan/${encodeURIComponent(item.sessionId)}`}
                    >
                      {item.title}
                    </Link>
                    <span className="placeCardMeta">
                      {item.cities.length > 0 ? item.cities.join(" · ") : "行程"} · {item.days} 天 · 预算{" "}
                      {Math.round(item.grandTotal)} 元
                    </span>
                    <span className="placeCardMeta">收藏于 {item.savedAt.slice(0, 10)}</span>
                  </div>
                  <button
                    className="btn btnGhost"
                    type="button"
                    onClick={() => handleRemoveFavorite(item.sessionId)}
                  >
                    取消收藏
                  </button>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <Toast message={toast} onClose={closeToast} tone="success" />
    </div>
  );
}