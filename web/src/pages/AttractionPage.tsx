import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { fetchAttraction } from "../api/catalog";
import type { Attraction } from "../api/catalog";
import BackBar from "../components/BackBar";
import EmptyState from "../components/EmptyState";
import PlaceImage from "../components/PlaceImage";
import RecoBlock from "../components/RecoBlock";
import Skeleton from "../components/Skeleton";
import Toast from "../components/Toast";
import { isTodo, toggleTodo } from "../storage/localStore";
import { openState, tagEmoji } from "../theme/palette";

function priceLabel(price: number): string {
  return price === 0 ? "免费" : `${price} 元`;
}

function splitPoints(text: string): string[] {
  return (text ?? "")
    .split(/[；;。\n]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 1);
}

export default function AttractionPage() {
  const { name = "" } = useParams();
  const [attraction, setAttraction] = useState<Attraction | null>(null);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [todoed, setTodoed] = useState(false);

  const closeToast = useCallback(() => setToast(""), []);

  useEffect(() => {
    setTodoed(isTodo(name));
  }, [name]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);

    fetchAttraction(name)
      .then((res) => {
        if (cancelled) return;
        setAttraction(res);
        setError("");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setNotFound(true);
        else setError(err instanceof ApiError ? err.detail : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [name]);

  if (loading)
    return (
      <>
        <BackBar to={attraction ? `/city/${encodeURIComponent(attraction.city)}` : "/"} />
        <Skeleton lines={6} />
      </>
    );

  if (notFound) {
    return (
      <>
        <BackBar to={attraction ? `/city/${encodeURIComponent(attraction.city)}` : "/"} />
        <EmptyState
          emoji="📍"
          title="未找到该景点"
          hint={`景点「${name}」暂不在目录中。`}
          action={
            <Link className="btn btnPrimary" to="/">
              返回首页
            </Link>
          }
        />
      </>
    );
  }

  if (error) {
    return (
      <>
        <BackBar to={attraction ? `/city/${encodeURIComponent(attraction.city)}` : "/"} />
        <section className="card">
          <p className="errorBar" role="alert">
            {error}
          </p>
          <Link className="btn btnGhost" to="/">
            返回首页
          </Link>
        </section>
      </>
    );
  }

  if (!attraction) {
    return (
      <>
        <BackBar to="/" />
        <EmptyState emoji="📍" title="暂无景点信息" hint="稍后再试或返回首页浏览其他景点。" />
      </>
    );
  }

  const open = openState(attraction.open_time);
  const meta = attraction.image_meta;
  const features = splitPoints(attraction.features);
  const tips = splitPoints(attraction.tips);

  function onToggleTodo() {
    if (!attraction) return;
    const added = toggleTodo({
      name: attraction.name,
      city: attraction.city,
      image: attraction.image,
      ticket_price: attraction.ticket_price,
      addedAt: new Date().toISOString(),
    });
    setTodoed(added);
    setToast(added ? "已加入想去清单" : "已从想去清单移除");
  }

  return (
    <div className="fadeIn">
      <BackBar to={attraction ? `/city/${encodeURIComponent(attraction.city)}` : "/"} />
      <PlaceImage
        src={attraction.image}
        fallbackSrc={attraction.image_fallback}
        name={attraction.name}
        city={attraction.city}
        ratio="16 / 9"
      />

      <header className="pageHeader">
        <h1 className="cardTitle">{attraction.name}</h1>
        <p className="muted">
          <Link to={`/city/${encodeURIComponent(attraction.city)}`}>{attraction.city}</Link> · 点赞{" "}
          {attraction.likes}
        </p>
        <div className="statRow">
          <span className="statChip">{priceLabel(attraction.ticket_price)}</span>
          <span className="statChip">{open.label}</span>
          <span className="statChip">{attraction.indoor ? "室内景点" : "室外景点"}</span>
        </div>
      </header>

      <div className="chipRow">
        <button className={todoed ? "btn btnGhost" : "btn btnPrimary"} type="button" onClick={onToggleTodo}>
          {todoed ? "已在想去清单（点击移除）" : "加入想去清单"}
        </button>
        <Link className="btn btnGhost" to={`/city/${encodeURIComponent(attraction.city)}`}>
          返回{attraction.city}
        </Link>
      </div>

      <section className="card">
        <div className="chipRow">
          {attraction.tags.map((tag) => (
            <span key={tag} className="tagPill">
              {tagEmoji(tag)} {tag}
            </span>
          ))}
        </div>
        <p>地址：{attraction.address}</p>
        <p>开放时间：{attraction.open_time}</p>
        <p className="muted">
          {attraction.indoor ? "室内景点，雨天也可安排" : "室外景点，注意天气"}
        </p>
      </section>

      <section className="card">
        <h2 className="cardTitle">✨ 看点</h2>
        {features.length === 0 ? (
          <p className="muted">{attraction.features || "暂无看点介绍"}</p>
        ) : (
          <ul>
            {features.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2 className="cardTitle">🎒 贴士</h2>
        {tips.length === 0 ? (
          <p className="muted">{attraction.tips || "暂无贴士"}</p>
        ) : (
          <ul>
            {tips.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}
      </section>

      <RecoBlock kind="attraction" name={attraction.name} />

      {meta && (meta.author || meta.license || meta.source_url) ? (
        <p className="muted">
          图片来源：
          {meta.source_url ? (
            <a href={meta.source_url} target="_blank" rel="noreferrer">
              {meta.author || "原始页面"}
            </a>
          ) : (
            meta.author
          )}
          {meta.license ? ` · ${meta.license}` : ""}
        </p>
      ) : null}

      <Toast message={toast} onClose={closeToast} tone="success" />
    </div>
  );
}