import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { startPlanAsync } from "../api/plan";
import { readPrefs, TASTE_OPTIONS } from "../storage/localStore";

const AGE_GROUPS = ["年轻人", "老人", "小孩", "家庭", "商务"];
const HOTEL_LEVELS = ["经济", "舒适", "高档"];
const TRANSPORT_PREFS = ["高铁", "飞机", "都可以"];

interface CityRow {
  city: string;
  days: number;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function addDays(date: string, offset: number): string {
  const base = new Date(`${date}T00:00:00`);
  if (Number.isNaN(base.getTime())) return date;
  base.setDate(base.getDate() + offset);
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}`;
}

function parseTastes(raw: string): string[] {
  return raw
    .split(/[,，、;；\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function tastesFromPrefs(values: string[]): string {
  return values
    .map((value) => TASTE_OPTIONS.find((option) => option.value === value)?.label ?? value)
    .join("，");
}

function hotelLevelFromBudget(budget: number | undefined): string {
  if (budget === undefined || !Number.isFinite(budget)) return HOTEL_LEVELS[1];
  if (budget < 200) return HOTEL_LEVELS[0];
  if (budget < 500) return HOTEL_LEVELS[1];
  return HOTEL_LEVELS[2];
}

export default function PlanQuickPage() {
  const navigate = useNavigate();
  const prefs = readPrefs();

  const [departure, setDeparture] = useState(prefs.address?.trim() || "北京");
  const [cities, setCities] = useState<CityRow[]>([{ city: "大理", days: 3 }]);
  const [depDate, setDepDate] = useState("2026-07-01");
  const [returnDate, setReturnDate] = useState("");
  const [people, setPeople] = useState(2);
  const [ageGroup, setAgeGroup] = useState(AGE_GROUPS[0]);
  const [tastes, setTastes] = useState(tastesFromPrefs(prefs.tastes));
  const [hotelLevel, setHotelLevel] = useState(hotelLevelFromBudget(prefs.accommodation_budget));
  const [transportPref, setTransportPref] = useState(TRANSPORT_PREFS[0]);
  const [budget, setBudget] = useState(prefs.total_budget ?? 3000);

  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const totalDays = cities.reduce((sum, row) => sum + (Number(row.days) || 0), 0);

  function updateCity(index: number, patch: Partial<CityRow>) {
    setCities((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function removeCity(index: number) {
    setCities((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)));
  }

  function addCity() {
    setCities((prev) => [...prev, { city: "", days: 1 }]);
  }

  function validate(cleanCities: CityRow[]): string {
    if (!departure.trim()) return "请填写出发城市";
    if (cleanCities.length === 0) return "请至少填写一个目的地城市";
    if (totalDays <= 0) return "总天数必须大于 0";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(depDate)) return "请填写合法的出发日期";
    if (!Number.isFinite(people) || people < 1) return "出行人数至少为 1";
    if (!Number.isFinite(budget) || budget < 0) return "人均预算不能为负数";
    return "";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const cleanCities = cities
      .map((row) => ({ city: row.city.trim(), days: Number(row.days) || 0 }))
      .filter((row) => row.city.length > 0);

    const problem = validate(cleanCities);
    if (problem) {
      setError(problem);
      return;
    }

    const days = cleanCities.reduce((sum, row) => sum + row.days, 0);
    const userData = {
      departure: departure.trim(),
      destination: cleanCities[0].city,
      cities: cleanCities,
      is_multi_city: cleanCities.length > 1,
      days,
      people: Number(people),
      dep_date: depDate,
      return_date: returnDate || addDays(depDate, Math.max(days - 1, 0)),
      age_group: ageGroup,
      tastes: parseTastes(tastes),
      attraction_prefs: [],
      transport_pref: transportPref,
      hotel_level: hotelLevel,
      hotel_location: "subway",
      budget: Number(budget),
    };

    setSubmitting(true);
    setError("");
    try {
      const result = await startPlanAsync(userData);
      navigate(`/plan/${encodeURIComponent(result.session_id)}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
      setSubmitting(false);
    }
  }

  return (
    <section className="card">
      <h2 className="cardTitle">快速制定</h2>

      {error ? (
        <p className="errorBar" role="alert">
          {error}
        </p>
      ) : null}

      <form className="formGrid" onSubmit={handleSubmit}>
        <label className="field">
          <span>出发城市</span>
          <input value={departure} onChange={(e) => setDeparture(e.target.value)} placeholder="如 北京" />
        </label>

        <label className="field">
          <span>出发日期</span>
          <input type="date" value={depDate} onChange={(e) => setDepDate(e.target.value)} />
        </label>

        <label className="field">
          <span>返程日期（留空自动推算）</span>
          <input type="date" value={returnDate} onChange={(e) => setReturnDate(e.target.value)} />
        </label>

        <label className="field">
          <span>出行人数</span>
          <input
            type="number"
            min={1}
            value={people}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setPeople(Number(e.target.value))}
          />
        </label>

        <label className="field">
          <span>人群类型</span>
          <select value={ageGroup} onChange={(e) => setAgeGroup(e.target.value)}>
            {AGE_GROUPS.map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>住宿档次</span>
          <select value={hotelLevel} onChange={(e) => setHotelLevel(e.target.value)}>
            {HOTEL_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>交通偏好</span>
          <select value={transportPref} onChange={(e) => setTransportPref(e.target.value)}>
            {TRANSPORT_PREFS.map((pref) => (
              <option key={pref} value={pref}>
                {pref}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>人均预算（元）</span>
          <input type="number" min={0} value={budget} onChange={(e) => setBudget(Number(e.target.value))} />
        </label>

        <label className="field fieldWide">
          <span>口味偏好（逗号分隔，可留空）</span>
          <input value={tastes} onChange={(e) => setTastes(e.target.value)} placeholder="如 川菜, 素食" />
        </label>

        <div className="field fieldWide">
          <span>目的地城市与天数（合计 {totalDays} 天）</span>
          {cities.map((row, index) => (
            <div className="cityRow" key={index}>
              <input
                value={row.city}
                placeholder="城市名"
                onChange={(e) => updateCity(index, { city: e.target.value })}
              />
              <input
                type="number"
                min={1}
                value={row.days}
                onChange={(e) => updateCity(index, { days: Number(e.target.value) })}
              />
              <button type="button" className="btn btnGhost" onClick={() => removeCity(index)}>
                删除
              </button>
            </div>
          ))}
          <button type="button" className="btn btnGhost" onClick={addCity}>
            添加城市
          </button>
        </div>

        <div className="field fieldWide">
          <button type="submit" className="btn btnPrimary" disabled={submitting}>
            {submitting ? "创建计划中…" : "生成行程"}
          </button>
        </div>
      </form>
    </section>
  );
}