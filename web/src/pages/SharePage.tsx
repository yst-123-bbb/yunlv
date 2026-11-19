import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, ApiError } from "../api/client";
import type { BudgetBreakdown, PlanSession } from "../api/client";

const BUDGET_ROWS: { key: keyof BudgetBreakdown; label: string }[] = [
  { key: "transport", label: "往返交通" },
  { key: "city_transport", label: "市内交通" },
  { key: "hotel", label: "住宿" },
  { key: "tickets", label: "门票" },
  { key: "food", label: "餐饮" },
  { key: "shopping", label: "购物" },
  { key: "reserve", label: "备用金" },
];

function money(value?: number): string {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} 元` : "-";
}

export default function SharePage() {
  const { shortId = "" } = useParams();
  const [plan, setPlan] = useState<PlanSession | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiGet<{ plan: PlanSession }>(`/api/share/${encodeURIComponent(shortId)}`)
      .then((res) => {
        if (cancelled) return;
        setPlan(res.plan);
        setError("");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.detail : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [shortId]);

  if (loading) return <p className="muted">正在读取分享行程…</p>;

  if (error) {
    return (
      <section className="card">
        <p className="errorBar" role="alert">
          {error}
        </p>
        <Link className="btn btnGhost" to="/">
          自己也规划一个
        </Link>
      </section>
    );
  }

  if (!plan) return <p className="muted">暂无分享行程</p>;

  const userData = plan.user_data ?? {};
  const cities = Array.isArray(userData.cities) ? (userData.cities as { city?: string; days?: number }[]) : [];
  const budget = plan.budget;

  return (
    <div className="planLayout">
      <section className="card">
        <h2 className="cardTitle">
          {String(userData.departure ?? "出发地")} →{" "}
          {cities.length > 0 ? cities.map((c) => c.city ?? "").join(" → ") : String(userData.destination ?? "")}
        </h2>
        <div className="summary">
          <span>行程天数：{String(userData.days ?? plan.itinerary.length)} 天</span>
          <span>出行人数：{String(userData.people ?? "-")} 人</span>
          <span>出发日期：{String(userData.dep_date ?? "-")}</span>
          <span>只读分享</span>
        </div>
      </section>

      <section className="card">
        <h2 className="cardTitle">每日行程</h2>
        {plan.itinerary.length === 0 ? (
          <p className="muted">行程尚未生成</p>
        ) : (
          plan.itinerary.map((day) => (
            <div key={`${day.day}-${day.date}`}>
              <h3 className="cardTitle">
                第 {day.day} 天 · {day.date}
              </h3>
              {day.items.length === 0 ? (
                <p className="muted">当日暂无安排</p>
              ) : (
                <table className="budgetTable">
                  <tbody>
                    {day.items.map((item, index) => (
                      <tr key={`${day.day}-${index}-${item.name}`}>
                        <th scope="row">{item.name}</th>
                        <td>
                          {item.start ?? "-"} – {item.end ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))
        )}
      </section>

      <section className="card">
        <h2 className="cardTitle">预算明细</h2>
        {budget ? (
          <table className="budgetTable">
            <tbody>
              {BUDGET_ROWS.map((row) => (
                <tr key={String(row.key)}>
                  <th scope="row">{row.label}</th>
                  <td>{money(budget[row.key])}</td>
                </tr>
              ))}
              <tr className="budgetTotal">
                <th scope="row">合计</th>
                <td>{money(budget.grand_total)}</td>
              </tr>
              <tr className="budgetTotal">
                <th scope="row">人均</th>
                <td>{money(budget.per_person)}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="muted">预算尚未生成</p>
        )}
      </section>

      <section className="card">
        <Link className="btn btnPrimary" to="/">
          自己也规划一个
        </Link>
      </section>
    </div>
  );
}