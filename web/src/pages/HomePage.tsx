import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { fetchComments, fetchHot } from "../api/catalog";
import type { Attraction, CityBrief, Comment } from "../api/catalog";
import EmptyState from "../components/EmptyState";
import PlaceImage from "../components/PlaceImage";
import Skeleton from "../components/Skeleton";
import { cityInitial, cityTheme, openState, tagEmoji } from "../theme/palette";

const HOT_COMMENT_LIMIT = 5;

const OPEN_STATE_TONE: Record<string, string> = {
  open: "var(--accent2)",
  always: "var(--accent2)",
  closed: "var(--accent)",
  unknown: "var(--muted)",
};

function priceLabel(ticketPrice: number): string {
  return ticketPrice > 0 ? `门票 ${ticketPrice} 元` : "免费";
}

export default function HomePage() {
  const navigate = useNavigate();

  const [keyword, setKeyword] = useState("");
  const [cities, setCities] = useState<CityBrief[]>([]);
  const [attractions, setAttractions] = useState<Attraction[]>([]);
  const [commentCity, setCommentCity] = useState("");
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadHot() {
      setLoading(true);
      setError("");
      try {
        const hot = await fetchHot();
        if (cancelled) return;
        setCities(hot.cities);
        setAttractions(hot.attractions);

        const firstCity = hot.cities[0];
        if (!firstCity) {
          setCommentCity("");
          setComments([]);
          return;
        }

        setCommentCity(firstCity.name);
        try {
          const items = await fetchComments(firstCity.name, HOT_COMMENT_LIMIT);
          if (!cancelled) setComments(items);
        } catch {
          // 评语缺失不影响首页主体，按空数据处理（板块隐藏）
          if (!cancelled) setComments([]);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadHot();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = keyword.trim();
    if (!q) return;
    navigate(`/search?q=${encodeURIComponent(q)}`);
  }

  const isEmpty = !loading && cities.length === 0 && attractions.length === 0;

  return (
    <section>
      <header className="heroBanner">
        <h1 className="heroTitle">云旅 · 搜一座城，看一片景</h1>
        <p className="heroSub">热门城市、宝藏景点与真实评语，一次逛遍</p>
        <form className="heroSearchLight" onSubmit={handleSearch}>
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索城市或景点，例如 北京、西湖"
            aria-label="搜索城市或景点"
          />
          <button className="btn btnPrimary" type="submit">
            搜索
          </button>
        </form>
      </header>

      {error ? <div className="errorBar">加载失败：{error}</div> : null}

      {loading ? (
        <Skeleton lines={6} className="homeSkeleton" />
      ) : isEmpty ? (
        <EmptyState
          emoji="🏙️"
          title="暂无热门推荐"
          hint="稍后再试，或直接搜索想去的地方"
          action={
            <Link className="btn btnPrimary" to="/search">
              去搜索
            </Link>
          }
        />
      ) : (
        <>
          {cities.length > 0 ? (
            <>
              <h2 className="sectionTitle">🔥 热门城市</h2>
              <div className="gridCards">
                {cities.map((city) => {
                  const theme = cityTheme(city.name);
                  return (
                    <Link
                      key={city.name}
                      className="cityCard"
                      to={`/city/${encodeURIComponent(city.name)}`}
                    >
                      <span
                        className="cityBadge"
                        style={{ background: `linear-gradient(135deg, ${theme.from}, ${theme.to})` }}
                        aria-hidden="true"
                      >
                        {cityInitial(city.name)}
                      </span>
                      <span>
                        <strong className="placeCardTitle">{city.name}</strong>
                        <span className="placeCardMeta">
                          {city.province} · {city.tag}
                        </span>
                        {typeof city.attraction_count === "number" ? (
                          <span className="placeCardMeta">{city.attraction_count} 个景点</span>
                        ) : null}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </>
          ) : null}

          {attractions.length > 0 ? (
            <>
              <h2 className="sectionTitle">📍 热门景点</h2>
              <div className="gridCards">
                {attractions.map((spot, index) => {
                  const state = openState(spot.open_time);
                  return (
                    <Link
                      key={`${spot.city}-${spot.name}`}
                      className="placeCard"
                      to={`/attraction/${encodeURIComponent(spot.name)}`}
                    >
                      <div style={{ position: "relative" }}>
                        <PlaceImage src={spot.image} name={spot.name} city={spot.city} />
                        <span className="rankBadge">No.{index + 1}</span>
                      </div>
                      <strong className="placeCardTitle">{spot.name}</strong>
                      <span className="placeCardMeta">
                        {spot.city} · {spot.address}
                      </span>
                      <div className="statRow">
                        {spot.tags.slice(0, 3).map((tag) => (
                          <span key={tag} className="tagPill">
                            {tagEmoji(tag)} {tag}
                          </span>
                        ))}
                      </div>
                      <div className="statRow">
                        <span className="statChip">{priceLabel(spot.ticket_price)}</span>
                        <span className="statChip" style={{ color: OPEN_STATE_TONE[state.state] }}>
                          {state.label}
                        </span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </>
          ) : null}

          {comments.length > 0 ? (
            <>
              <h2 className="sectionTitle">💬 网友评语 · {commentCity}</h2>
              <div className="gridCards">
                {comments.slice(0, HOT_COMMENT_LIMIT).map((comment) => (
                  <article key={comment.id} className="commentCard">
                    <p className="commentText">{comment.text}</p>
                    <p className="commentMeta">
                      {comment.author} · {commentCity}
                      {comment.source_url ? (
                        <>
                          {" · "}
                          <a href={comment.source_url} target="_blank" rel="noreferrer">
                            来源
                          </a>
                        </>
                      ) : null}
                    </p>
                  </article>
                ))}
              </div>
            </>
          ) : null}
        </>
      )}
    </section>
  );
}