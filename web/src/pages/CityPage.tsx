import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { fetchCity, fetchComments } from "../api/catalog";
import type { Attraction, CityBrief, Comment } from "../api/catalog";
import BackBar from "../components/BackBar";
import EmptyState from "../components/EmptyState";
import PlaceImage from "../components/PlaceImage";
import RecoBlock from "../components/RecoBlock";
import Skeleton from "../components/Skeleton";
import { cityInitial, cityTheme, openState, tagEmoji } from "../theme/palette";

function priceLabel(price: number): string {
  return price === 0 ? "免费" : `${price} 元`;
}

export default function CityPage() {
  const { name = "" } = useParams();
  const [city, setCity] = useState<CityBrief | null>(null);
  const [attractions, setAttractions] = useState<Attraction[]>([]);
  const [comments, setComments] = useState<Comment[]>([]);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);

    fetchCity(name)
      .then((res) => {
        if (cancelled) return;
        setCity(res.city);
        setAttractions(res.attractions);
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

    fetchComments(name)
      .then((items) => {
        if (!cancelled) setComments(items);
      })
      .catch(() => {
        // 评语为可选板块：读取失败时静默隐藏，不影响主体内容
        if (!cancelled) setComments([]);
      });

    return () => {
      cancelled = true;
    };
  }, [name]);

  if (loading)
    return (
      <>
        <BackBar to="/" />
        <Skeleton lines={6} />
      </>
    );

  if (notFound) {
    return (
      <>
        <BackBar to="/" />
        <EmptyState
          emoji="🗺️"
          title="未找到该城市"
          hint={`城市「${name}」暂不在目录中。`}
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
        <BackBar to="/" />
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

  if (!city) {
    return (
      <>
        <BackBar to="/" />
        <EmptyState emoji="🗺️" title="暂无城市信息" hint="稍后再试或返回首页浏览其他城市。" />
      </>
    );
  }

  const theme = cityTheme(city.name);

  return (
    <div className="fadeIn">
      <BackBar to="/" />
      <header
        className="heroBanner"
        style={{ background: `linear-gradient(135deg, ${theme.from}, ${theme.to})` }}
      >
        <div className="statRow">
          <span className="cityBadge" style={{ background: "rgba(255, 255, 255, 0.24)" }}>
            {cityInitial(city.name)}
          </span>
          <div>
            <h1 className="heroTitle">{city.name}</h1>
            <p className="heroSub">
              {city.province} · {city.tag} · {attractions.length} 个景点
            </p>
          </div>
        </div>

      </header>

      <div className="chipRow">
        <Link
          className="btn btnPrimary"
          to={`/cities/compare?a=${encodeURIComponent(city.name)}`}
        >
          与其他城市对比
        </Link>
      </div>

      <h2 className="sectionTitle">🧭 城市看点</h2>
      {city.spots.length === 0 ? (
        <EmptyState emoji="📝" title="暂无看点" hint="该城市的看点仍在补充中。" />
      ) : (
        <div className="statRow">
          {city.spots.map((spot) => (
            <span key={spot} className="tagPill">
              {spot}
            </span>
          ))}
        </div>
      )}

      <h2 className="sectionTitle">🎯 景点推荐</h2>
      {attractions.length === 0 ? (
        <EmptyState emoji="🏞️" title="暂无景点" hint="我们正在补充该城市的景点信息。" />
      ) : (
        <div className="gridCards">
          {attractions.map((attraction) => {
            const open = openState(attraction.open_time);
            return (
              <Link
                key={attraction.name}
                className="placeCard"
                to={`/attraction/${encodeURIComponent(attraction.name)}`}
              >
                <PlaceImage
                  src={attraction.image}
                  fallbackSrc={attraction.image_fallback}
                  name={attraction.name}
                  city={attraction.city}
                />
                <span className="placeCardTitle">{attraction.name}</span>
                <span className="placeCardMeta">
                  {priceLabel(attraction.ticket_price)} · {open.label}
                </span>
                <span className="statRow">
                  {attraction.tags.map((tag) => (
                    <span key={tag} className="tagPill">
                      {tagEmoji(tag)} {tag}
                    </span>
                  ))}
                </span>
              </Link>
            );
          })}
        </div>
      )}

      <RecoBlock kind="city" name={city.name} />

      {comments.length > 0 ? (
        <>
          <h2 className="sectionTitle">💬 网友评语</h2>
          <div className="gridCards">
            {comments.map((comment) => (
              <article key={comment.id} className="commentCard">
                <p className="commentText">{comment.text}</p>
                <p className="commentMeta">
                  {comment.author} · 点赞 {comment.likes}
                </p>
              </article>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}