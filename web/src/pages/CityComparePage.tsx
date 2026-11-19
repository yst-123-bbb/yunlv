import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { fetchCities, fetchCity } from "../api/catalog";
import type { Attraction, CityBrief } from "../api/catalog";
import EmptyState from "../components/EmptyState";
import Skeleton from "../components/Skeleton";
import { cityInitial, cityTheme } from "../theme/palette";

interface CitySide {
  city: CityBrief;
  attractions: Attraction[];
}

function joinOrDash(items: string[]): string {
  return items.length > 0 ? items.join("、") : "—";
}

export default function CityComparePage() {
  const [params, setParams] = useSearchParams();
  const a = (params.get("a") ?? "").trim();
  const b = (params.get("b") ?? "").trim();
  const [left, setLeft] = useState<CitySide | null>(null);
  const [right, setRight] = useState<CitySide | null>(null);
  const [candidates, setCandidates] = useState<CityBrief[]>([]);
  const [error, setError] = useState("");
  const [missing, setMissing] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setMissing("");

    if (!a || !b) {
      setLeft(null);
      setRight(null);
      fetchCities()
        .then((items) => {
          if (!cancelled) setCandidates(items);
        })
        .catch((err: unknown) => {
          if (!cancelled) setError(err instanceof ApiError ? err.detail : String(err));
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
      return () => {
        cancelled = true;
      };
    }

    Promise.all([fetchCity(a), fetchCity(b)])
      .then(([first, second]) => {
        if (cancelled) return;
        setLeft(first);
        setRight(second);
        setCandidates([]);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setMissing(err.detail);
        else setError(err instanceof ApiError ? err.detail : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [a, b]);

  function pick(name: string) {
    const next = new URLSearchParams(params);
    if (!a) next.set("a", name);
    else next.set("b", name);
    setParams(next);
  }

  if (loading) return <Skeleton lines={6} />;

  if (error) {
    return (
      <section className="card">
        <p className="errorBar" role="alert">
          {error}
        </p>
        <Link className="btn btnGhost" to="/">
          返回首页
        </Link>
      </section>
    );
  }

  if (missing) {
    return (
      <EmptyState
        emoji="🗺️"
        title="未找到要对比的城市"
        hint="所选城市暂不在目录中，请重新选择。"
        action={
          <Link className="btn btnPrimary" to="/cities/compare">
            重新选择城市
          </Link>
        }
      />
    );
  }

  if (!left || !right) {
    return (
      <div className="fadeIn">
        <header className="heroBanner">
          <h1 className="heroTitle">城市对比</h1>
          <p className="heroSub">选择两座城市，并排查看省份、看点与代表景点。</p>
        </header>
        <h2 className="sectionTitle">{a ? `为「${a}」选择对比城市` : "选择第一座城市"}</h2>
        {candidates.length === 0 ? (
          <EmptyState emoji="🏙️" title="暂无可选城市" hint="城市目录读取失败或为空。" />
        ) : (
          <div className="chipRow">
            {candidates.map((item) => (
              <button
                key={item.name}
                className="chip"
                type="button"
                onClick={() => pick(item.name)}
                disabled={item.name === a || item.name === b}
              >
                {item.name}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  const leftTheme = cityTheme(left.city.name);
  const rightTheme = cityTheme(right.city.name);

  return (
    <div className="fadeIn">
      <header className="heroBanner">
        <h1 className="heroTitle">城市对比</h1>
        <p className="heroSub">
          {left.city.name} vs {right.city.name}
        </p>
      </header>

      <h2 className="sectionTitle">🏙️ 并排对比</h2>
      <div className="compareGrid">
        <Link className="cityCard" to={`/city/${encodeURIComponent(left.city.name)}`}>
          <span
            className="cityBadge"
            style={{ background: `linear-gradient(135deg, ${leftTheme.from}, ${leftTheme.to})` }}
          >
            {cityInitial(left.city.name)}
          </span>
          <div>
            <strong>{left.city.name}</strong>
            <div className="muted">{left.city.province}</div>
          </div>
        </Link>
        <Link className="cityCard" to={`/city/${encodeURIComponent(right.city.name)}`}>
          <span
            className="cityBadge"
            style={{ background: `linear-gradient(135deg, ${rightTheme.from}, ${rightTheme.to})` }}
          >
            {cityInitial(right.city.name)}
          </span>
          <div>
            <strong>{right.city.name}</strong>
            <div className="muted">{right.city.province}</div>
          </div>
        </Link>
      </div>

      <section className="card">
        <div className="compareRow">
          <span className="muted">省份</span>
          <span>{left.city.province}</span>
          <span>{right.city.province}</span>
        </div>
        <div className="compareRow">
          <span className="muted">标签</span>
          <span>{left.city.tag}</span>
          <span>{right.city.tag}</span>
        </div>
        <div className="compareRow">
          <span className="muted">看点</span>
          <span>{joinOrDash(left.city.spots)}</span>
          <span>{joinOrDash(right.city.spots)}</span>
        </div>
        <div className="compareRow">
          <span className="muted">景点数</span>
          <span>{left.attractions.length}</span>
          <span>{right.attractions.length}</span>
        </div>
        <div className="compareRow">
          <span className="muted">代表景点</span>
          <span>{joinOrDash(left.attractions.slice(0, 3).map((item) => item.name))}</span>
          <span>{joinOrDash(right.attractions.slice(0, 3).map((item) => item.name))}</span>
        </div>
      </section>

      <div className="chipRow">
        <Link className="btn btnGhost" to="/cities/compare">
          重新选择城市
        </Link>
      </div>
    </div>
  );
}