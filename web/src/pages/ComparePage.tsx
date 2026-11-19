import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, ApiError } from "../api/client";
import type { PlanSession } from "../api/client";

const MAX_TEMPLATES = 3;

const COMPARE_ROWS: { key: keyof NonNullable<PlanSession["budget"]>; label: string }[] = [
  { key: "transport", label: "交通" },
  { key: "hotel", label: "住宿" },
  { key: "tickets", label: "门票" },
  { key: "food", label: "餐饮" },
];

function money(value?: number): string {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} 元` : "-";
}

function summaryOf(state: PlanSession): string {
  const data = state.user_data ?? {};
  const cities = Array.isArray(data.cities) ? (data.cities as { city?: string }[]) : [];
  const route =
    cities.length > 0
      ? cities.map((city) => city.city ?? "").filter(Boolean).join(" → ")
      : String(data.destination ?? "");
  const days = String(data.days ?? state.itinerary.length);
  return `${route || "未命名路线"} · ${days} 天 · ${String(data.people ?? "-")} 人`;
}

export default function ComparePage() {
  const [names, setNames] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [states, setStates] = useState<Record<string, PlanSession>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ items: string[] }>("/api/templates")
      .then((res) => {
        if (cancelled) return;
        const items = Array.isArray(res.items) ? res.items : [];
        setNames(items);
        setSelected(items.slice(0, MAX_TEMPLATES));
        setError("");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const missing = selected.filter((name) => states[name] === undefined);
    if (missing.length === 0) return;

    let cancelled = false;
    const loadOne = (name: string) =>
      apiGet<{ state: PlanSession }>(`/api/templates/${encodeURIComponent(name)}`)
        .then((res) => [name, res.state] as [string, PlanSession])
        .catch((err) => {
          if (!cancelled) setError(err instanceof ApiError ? err.detail : String(err));
          return null;
        });

    Promise.all(missing.map(loadOne)).then((pairs) => {
      if (cancelled) return;
      const loaded = pairs.filter((pair): pair is [string, PlanSession] => pair !== null);
      if (loaded.length === 0) return;
      setStates((prev) => {
        const next = { ...prev };
        for (const [name, state] of loaded) next[name] = state;
        return next;
      });
    });

    return () => {
      cancelled = true;
    };
  }, [selected, states]);

  const toggle = useCallback((name: string) => {
    setSelected((prev) => {
      if (prev.includes(name)) return prev.filter((item) => item !== name);
      if (prev.length >= MAX_TEMPLATES) return prev;
      return [...prev, name];
    });
  }, []);

  const columns = selected.filter((name) => states[name] !== undefined);

  if (loading) return <p className="muted">正在读取模板…</p>;

  return (
    <div className="planLayout">
      <section className="card">
        <h2 className="cardTitle">模板对比</h2>
        <p className="muted">选择 2–3 个模板，对比交通 / 住宿 / 门票 / 餐饮与总额。</p>
        {names.length === 0 ? (
          <p className="muted">还没有保存的模板，先在行程页保存一个模板。</p>
        ) : (
          <div className="summary">
            {names.map((name) => {
              const checked = selected.includes(name);
              const disabled = !checked && selected.length >= MAX_TEMPLATES;
              return (
                <label key={name}>
                  <input type="checkbox" checked={checked} disabled={disabled} onChange={() => toggle(name)} />
                  {name}
                </label>
              );
            })}
          </div>
        )}
        {error && (
          <p className="errorBar" role="alert">
            {error}
          </p>
        )}
        <Link className="btn btnGhost" to="/">
          返回填写行程
        </Link>
      </section>

      {columns.length > 0 && (
        <section className="card">
          <table className="budgetTable">
            <thead>
              <tr>
                <th scope="col">项目</th>
                {columns.map((name) => (
                  <th key={name} scope="col">
                    {name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">路线</th>
                {columns.map((name) => (
                  <td key={name}>{summaryOf(states[name])}</td>
                ))}
              </tr>
              {COMPARE_ROWS.map((row) => (
                <tr key={String(row.key)}>
                  <th scope="row">{row.label}</th>
                  {columns.map((name) => (
                    <td key={name}>{money(states[name].budget?.[row.key])}</td>
                  ))}
                </tr>
              ))}
              <tr className="budgetTotal">
                <th scope="row">总额</th>
                {columns.map((name) => (
                  <td key={name}>{money(states[name].budget?.grand_total)}</td>
                ))}
              </tr>
              <tr className="budgetTotal">
                <th scope="row">人均</th>
                {columns.map((name) => (
                  <td key={name}>{money(states[name].budget?.per_person)}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}