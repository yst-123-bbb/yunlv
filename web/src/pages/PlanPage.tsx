import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiPost, ApiError } from "../api/client";
import type { PlanSession } from "../api/client";
import { fetchBudgetTiers, fetchPlanEnriched, replanWeather, startPlanAsync } from "../api/plan";
import type { BudgetTier, BudgetTiers, DayProfile, EnrichedPlanSession } from "../api/plan";
import PlanProgress from "../components/PlanProgress";
import TransferPanel from "../components/TransferPanel";
import TimelineMap from "../components/TimelineMap";
import ItineraryEditor from "../components/ItineraryEditor";
import CorrectionForm from "../components/CorrectionForm";
import Toast from "../components/Toast";
import BackBar from "../components/BackBar";
import { isFavorite, toggleFavorite } from "../storage/localStore";

const BUDGET_ROWS: { key: keyof NonNullable<PlanSession["budget"]>; label: string }[] = [
  { key: "transport", label: "往返交通" },
  { key: "city_transport", label: "市内交通" },
  { key: "hotel", label: "住宿" },
  { key: "tickets", label: "门票" },
  { key: "food", label: "餐饮" },
  { key: "shopping", label: "购物" },
  { key: "reserve", label: "备用金" },
];

const FIT_TEXT: Record<BudgetTier["fit"], string> = {
  under: "预算低于该档",
  within: "当前档位",
  over: "预算高于该档",
};

const INTENSITY_LEVEL: Record<DayProfile["intensity"], number> = { low: 1, mid: 2, high: 3 };

const INTENSITY_LABEL: Record<DayProfile["intensity"], string> = {
  low: "轻松",
  mid: "适中",
  high: "高强度",
};

const INTENSITY_CLASS: Record<DayProfile["intensity"], string> = {
  low: "intensityLow",
  mid: "intensityMid",
  high: "intensityHigh",
};

const POLL_INTERVAL_MS = 2000;
const STALL_POLLS = 3;
const WAIT_LIMIT_SECONDS = 180;
const TIMEOUT_TEXT = "生成时间较长，请稍后刷新重试";

function money(value?: number): string {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)} 元` : "-";
}

export default function PlanPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const [state, setState] = useState<EnrichedPlanSession | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [waitedSeconds, setWaitedSeconds] = useState(0);
  const [timedOut, setTimedOut] = useState(false);
  const [retrying, setRetrying] = useState(false);

  const complete = state !== null && state.stage >= 6;

  useEffect(() => {
    let cancelled = false;
    let stopped = false;
    let timer: number | null = null;
    let previousStage: number | null = null;
    let unchangedPolls = 0;
    const startedAt = Date.now();

    const stopPolling = () => {
      stopped = true;
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };

    const poll = async () => {
      try {
        const res = await fetchPlanEnriched(sessionId);
        if (cancelled) return;
        setState(res);
        setError("");
        setLoading(false);
        const waited = Math.round((Date.now() - startedAt) / 1000);
        setWaitedSeconds(waited);
        if (res.stage >= 6 || res.generation_error) {
          stopPolling();
          return;
        }
        unchangedPolls = previousStage === res.stage ? unchangedPolls + 1 : 0;
        previousStage = res.stage;
        if (unchangedPolls >= STALL_POLLS && waited > WAIT_LIMIT_SECONDS) {
          setTimedOut(true);
          stopPolling();
        }
      } catch (err) {
        if (cancelled) return;
        setLoading(false);
        setError(err instanceof ApiError ? err.detail : String(err));
        stopPolling();
      }
    };

    setState(null);
    setError("");
    setLoading(true);
    setWaitedSeconds(0);
    setTimedOut(false);
    void poll();
    timer = window.setInterval(() => {
      if (!stopped) void poll();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [sessionId]);

  const handleRetry = useCallback(async () => {
    if (!state) return;
    setRetrying(true);
    try {
      const created = await startPlanAsync(state.user_data);
      navigate(`/plan/${encodeURIComponent(created.session_id)}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setRetrying(false);
    }
  }, [state, navigate]);

  const [tiers, setTiers] = useState<BudgetTiers | null>(null);
  const [tiersError, setTiersError] = useState("");

  useEffect(() => {
    if (!complete) return;
    let cancelled = false;
    setTiers(null);
    setTiersError("");
    fetchBudgetTiers(sessionId)
      .then((res) => {
        if (!cancelled) setTiers(res);
      })
      .catch((err) => {
        if (!cancelled) setTiersError(err instanceof ApiError ? err.detail : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, complete]);

  // 行程编辑器只回传 PlanSession，这里保留既有强度画像避免区块闪空。
  const handleStateChange = useCallback((next: PlanSession) => {
    setState((prev) => ({ ...next, day_profile: prev?.day_profile ?? [] }));
  }, []);

  const activeSessionId = state?.session_id ?? sessionId;

  const [favorite, setFavorite] = useState(() => isFavorite(sessionId));

  useEffect(() => {
    setFavorite(isFavorite(activeSessionId));
  }, [activeSessionId]);

  const handleToggleFavorite = useCallback(() => {
    const favoriteCities = Array.isArray(state?.user_data.cities)
      ? (state.user_data.cities as { city?: unknown }[]).map((c) => String(c.city ?? "")).filter(Boolean)
      : [];
    const destination =
      favoriteCities.length > 0 ? favoriteCities.join("、") : String(state?.user_data.destination ?? "");
    const days = Number(state?.user_data.days ?? state?.itinerary.length ?? 0) || 0;
    const next = toggleFavorite({
      sessionId: activeSessionId,
      title: `${destination || "行程"} ${days} 天`,
      cities: favoriteCities,
      days,
      grandTotal: state?.budget?.grand_total ?? 0,
      savedAt: new Date().toISOString(),
    });
    setFavorite(next);
  }, [state, activeSessionId]);

  const [weatherByDay, setWeatherByDay] = useState<Record<string, string>>({});
  const [replanning, setReplanning] = useState(false);
  const [replanError, setReplanError] = useState("");
  const [toast, setToast] = useState("");

  const handleToastClose = useCallback(() => setToast(""), []);

  const handleWeatherChange = useCallback((day: number, value: string) => {
    setWeatherByDay((prev) => ({ ...prev, [String(day)]: value }));
  }, []);

  const handleReplan = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const payload: Record<string, string> = {};
      Object.entries(weatherByDay).forEach(([day, text]) => {
        const trimmed = text.trim();
        if (trimmed) payload[day] = trimmed;
      });
      if (Object.keys(payload).length === 0) {
        setReplanError("请至少为一天填写天气，例如「小雨」或「高温 36」");
        return;
      }
      setReplanning(true);
      setReplanError("");
      try {
        const res = await replanWeather(activeSessionId, payload);
        setState(res.state);
        setToast(`天气重排完成，${res.notes.length} 条调整提示`);
      } catch (err) {
        setReplanError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setReplanning(false);
      }
    },
    [weatherByDay, activeSessionId],
  );

  const [sharing, setSharing] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const [shareShortId, setShareShortId] = useState("");
  const [shareError, setShareError] = useState("");

  const handleShare = useCallback(async () => {
    setSharing(true);
    setShareError("");
    try {
      const res = await apiPost<{ short_id: string; url: string }>("/api/share", {
        session_id: activeSessionId,
      });
      setShareShortId(res.short_id);
      setShareUrl(res.url);
    } catch (err) {
      setShareError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setSharing(false);
    }
  }, [activeSessionId]);

  const [templateName, setTemplateName] = useState("");
  const [templateMessage, setTemplateMessage] = useState("");
  const [templateError, setTemplateError] = useState("");
  const [savingTemplate, setSavingTemplate] = useState(false);

  const handleSaveTemplate = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const name = templateName.trim();
      if (!name) return;
      setSavingTemplate(true);
      setTemplateMessage("");
      setTemplateError("");
      try {
        const res = await apiPost<{ name: string }>("/api/templates", {
          name,
          session_id: activeSessionId,
        });
        setTemplateMessage(`已保存模板：${res.name}`);
        setTemplateName("");
      } catch (err) {
        setTemplateError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        setSavingTemplate(false);
      }
    },
    [templateName, activeSessionId],
  );

  if (loading && !state) {
    return (
      <>
        <BackBar to="/plan/quick" />
        <p className="muted">正在读取行程…</p>
      </>
    );
  }

  if (!state) {
    return (
      <>
        <BackBar to="/plan/quick" />
        <section className="card">
          <p className="errorBar" role="alert">
            {error || "暂无行程数据"}
          </p>
          <Link className="btn btnGhost" to="/">
            返回重新填写
          </Link>
        </section>
      </>
    );
  }

  const progressError = state.generation_error || error || (timedOut ? TIMEOUT_TEXT : "");

  if (state.stage < 6) {
    return (
      <>
        <BackBar to="/plan/quick" />
        <PlanProgress
          stage={state.stage}
          error={progressError || undefined}
          waitedSeconds={waitedSeconds}
          onRetry={handleRetry}
          retrying={retrying}
        />
      </>
    );
  }

  const userData = state.user_data ?? {};
  const cities = Array.isArray(userData.cities) ? (userData.cities as { city?: string; days?: number }[]) : [];
  const budget = state.budget;
  const cutTier = tiers ? tiers.tiers.find((t) => t.fit === "within") ?? tiers.tiers[0] : null;

  return (
    <>
      <BackBar to="/plan/quick" />
      <div className="planLayout">
      <section className="card">
        <div className="pageHeader">
          <h2 className="cardTitle">
            {String(userData.departure ?? "出发地")} →{" "}
            {cities.length > 0 ? cities.map((c) => c.city ?? "").join(" → ") : String(userData.destination ?? "")}
          </h2>
          <button className="btn btnGhost" type="button" onClick={handleToggleFavorite}>
            {favorite ? "已收藏 ★" : "收藏行程 ☆"}
          </button>
        </div>
        <div className="summary">
          <span>行程天数：{String(userData.days ?? state.itinerary.length)} 天</span>
          <span>出行人数：{String(userData.people ?? "-")} 人</span>
          <span>出发日期：{String(userData.dep_date ?? "-")}</span>
          <span>当前阶段：{state.stage}/6</span>
        </div>
      </section>

      <section className="card">
        <h2 className="cardTitle">中转比价</h2>
        <TransferPanel
          origin={String(userData.departure ?? "")}
          dest={String(userData.destination ?? "")}
          people={Number(userData.people ?? 1) || 1}
        />
      </section>

      <section className="card">
        <h2 className="cardTitle">路线时间轴</h2>
        <TimelineMap itinerary={state.itinerary} />
      </section>

      <section className="card">
        <h2 className="cardTitle">每日行程（可拖拽调整顺序）</h2>
        <ItineraryEditor sessionId={state.session_id} itinerary={state.itinerary} onStateChange={handleStateChange} />
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
        <h2 className="cardTitle">预算档位</h2>
        {tiersError ? (
          <p className="errorBar" role="alert">
            {tiersError}
          </p>
        ) : null}
        {tiers ? (
          <>
            <div className="statRow">
              <span className="statChip">行程 {tiers.days} 天</span>
              <span className="statChip">出行 {tiers.people} 人</span>
              <span className="statChip">当前合计 {money(tiers.current_total)}</span>
            </div>
            <div className="gridCards">
              {tiers.tiers.map((tier) => (
                <div key={tier.tier} className={tier.fit === "within" ? "tierCard tierCardActive" : "tierCard"}>
                  <div className="cardTitle">{tier.label}</div>
                  <div className="tierRange">
                    {money(tier.low)} ~ {money(tier.high)}
                  </div>
                  <p className="muted">{FIT_TEXT[tier.fit]}</p>
                  {cutTier && cutTier.tier === tier.tier ? (
                    tier.cuts.length > 0 ? (
                      tier.cuts.map((cut, index) => (
                        <div className="cutItem" key={`${cut.kind}-${index}`}>
                          <span>{cut.label}</span>
                          <strong>省 {money(cut.save)}</strong>
                        </div>
                      ))
                    ) : (
                      <p className="muted">暂无削减建议</p>
                    )
                  ) : null}
                </div>
              ))}
            </div>
            {tiers.gap.to_economy ? (
              <p className="muted">比经济档上限多出 {money(tiers.gap.to_economy)}</p>
            ) : null}
          </>
        ) : tiersError ? null : (
          <p className="muted">正在计算预算档位…</p>
        )}
      </section>

      <section className="card">
        <h2 className="cardTitle">每日强度</h2>
        {state.day_profile.length === 0 ? (
          <p className="muted">暂无每日强度数据</p>
        ) : (
          <div>
            {state.day_profile.map((profile) => (
              <div className="dayProfileRow" key={profile.day}>
                <span>第{profile.day}天</span>
                <div>
                  <div className="intensityBar" role="img" aria-label={`强度：${INTENSITY_LABEL[profile.intensity]}`}>
                    {[1, 2, 3].map((level) => {
                      const active = level <= INTENSITY_LEVEL[profile.intensity];
                      return (
                        <span
                          key={level}
                          className={active ? INTENSITY_CLASS[profile.intensity] : undefined}
                          style={{
                            flex: 1,
                            height: 8,
                            borderRadius: 999,
                            background: active ? undefined : "var(--border)",
                          }}
                        />
                      );
                    })}
                  </div>
                  <div className="muted">
                    {profile.date || "日期待定"} · 步行 {profile.walk_km} km · 爬升 {profile.climb_m} m · 强度{" "}
                    {INTENSITY_LABEL[profile.intensity]}
                    {profile.elevator_ok ? " · 有电梯" : " · 无电梯"}
                  </div>
                  {profile.tips.length > 0 ? (
                    <div className="muted">
                      {profile.tips.map((tip, index) => (
                        <div key={index}>· {tip}</div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="cardTitle">天气重排</h2>
        <form className="weatherPanel" onSubmit={handleReplan}>
          {state.itinerary.map((day) => (
            <label className="field" key={day.day}>
              <span>
                第{day.day}天{day.date ? ` · ${day.date}` : ""}
              </span>
              <input
                type="text"
                value={weatherByDay[String(day.day)] ?? ""}
                placeholder="如：晴 / 小雨 / 高温 36"
                aria-label={`第${day.day}天天气`}
                onChange={(event) => handleWeatherChange(day.day, event.target.value)}
              />
            </label>
          ))}
          <button className="btn" type="submit" disabled={replanning}>
            {replanning ? "重排中…" : "按天气重排户外行程"}
          </button>
          {replanError ? (
            <p className="errorBar" role="alert">
              {replanError}
            </p>
          ) : null}
        </form>
      </section>

      <section className="card">
        <h2 className="cardTitle">导出</h2>
        <div className="summary">
          <a className="btn" href={`/api/plan/${encodeURIComponent(activeSessionId)}/export.ics`} download>
            下载日历(.ics)
          </a>
          <a className="btn" href={`/api/plan/${encodeURIComponent(activeSessionId)}/export.pdf`} download>
            下载行程单(.pdf)
          </a>
          <a className="btn" href={`/api/plan/${encodeURIComponent(activeSessionId)}/export.png`} download>
            下载长图(.png)
          </a>
        </div>
      </section>

      <section className="card">
        <h2 className="cardTitle">分享</h2>
        <button className="btn" type="button" onClick={handleShare} disabled={sharing}>
          {sharing ? "生成中…" : "生成分享链接"}
        </button>
        {shareError ? (
          <p className="errorBar" role="alert">
            {shareError}
          </p>
        ) : null}
        {shareUrl ? (
          <div className="summary">
            <a href={shareUrl}>{shareUrl}</a>
            <Link to={`/share/${shareShortId}`}>/share/{shareShortId}</Link>
          </div>
        ) : null}
      </section>

      <section className="card">
        <h2 className="cardTitle">保存为模板</h2>
        <form className="summary" onSubmit={handleSaveTemplate}>
          <input
            type="text"
            value={templateName}
            placeholder="模板名称"
            aria-label="模板名称"
            onChange={(event) => setTemplateName(event.target.value)}
          />
          <button className="btn" type="submit" disabled={!templateName.trim() || savingTemplate}>
            {savingTemplate ? "保存中…" : "保存为模板"}
          </button>
        </form>
        {templateMessage ? <p className="muted">{templateMessage}</p> : null}
        {templateError ? (
          <p className="errorBar" role="alert">
            {templateError}
          </p>
        ) : null}
      </section>

      <section className="card">
        <h2 className="cardTitle">这条数据有误？</h2>
        <CorrectionForm />
      </section>

      {toast ? <Toast message={toast} onClose={handleToastClose} /> : null}
      </div>
    </>
  );
}