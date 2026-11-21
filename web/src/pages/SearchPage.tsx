import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { fetchHot, searchAll, suggestPlaces } from "../api/catalog";
import type { Attraction, CityBrief } from "../api/catalog";
import BackBar from "../components/BackBar";
import EmptyState from "../components/EmptyState";
import PlaceImage from "../components/PlaceImage";
import Skeleton from "../components/Skeleton";
import { clearSearchHistory, pushSearchHistory, readPrefs, readSearchHistory } from "../storage/localStore";
import { tagEmoji } from "../theme/palette";

type ResultTab = "all" | "city" | "attraction";

const RESULT_TABS: { value: ResultTab; label: string }[] = [
  { value: "all", label: "全部" },
  { value: "city", label: "城市" },
  { value: "attraction", label: "景点" },
];

interface SuggestionBundle {
  cities: CityBrief[];
  attractions: Attraction[];
}

export default function SearchPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const keyword = (params.get("q") ?? "").trim();

  const [draft, setDraft] = useState(keyword);
  const [history, setHistory] = useState<string[]>(() => readSearchHistory());
  const [cities, setCities] = useState<CityBrief[]>([]);
  const [attractions, setAttractions] = useState<Attraction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<ResultTab>("all");
  const [suggestions, setSuggestions] = useState<SuggestionBundle | null>(null);
  const suggestSeq = useRef(0);

  useEffect(() => {
    setDraft(keyword);
  }, [keyword]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    const request = keyword ? searchAll(keyword) : fetchHot();
    request
      .then((res) => {
        if (cancelled) return;
        setCities(Array.isArray(res.cities) ? res.cities : []);
        setAttractions(Array.isArray(res.attractions) ? res.attractions : []);
        if (keyword) setHistory(pushSearchHistory(keyword));
      })
      .catch((err) => {
        if (cancelled) return;
        setCities([]);
        setAttractions([]);
        setError(err instanceof ApiError ? err.detail : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [keyword]);

  useEffect(() => {
    const q = draft.trim();
    const seq = suggestSeq.current + 1;
    suggestSeq.current = seq;
    if (!q) {
      setSuggestions(null);
      return;
    }

    const timer = setTimeout(() => {
      suggestPlaces(q)
        .then((res) => {
          if (suggestSeq.current !== seq) return;
          setSuggestions({
            cities: Array.isArray(res.cities) ? res.cities : [],
            attractions: Array.isArray(res.attractions) ? res.attractions : [],
          });
        })
        .catch(() => {
          if (suggestSeq.current === seq) setSuggestions(null);
        });
    }, 300);

    return () => {
      clearTimeout(timer);
    };
  }, [draft]);

  const sortedAttractions = useMemo(() => {
    const prefs = new Set(readPrefs().attraction_pref);
    return attractions
      .map((item, index) => ({
        item,
        index,
        score: item.tags.filter((tag) => prefs.has(tag)).length,
      }))
      .sort((a, b) => b.score - a.score || a.index - b.index)
      .map((entry) => entry.item);
  }, [attractions]);

  const submit = (value: string) => {
    const q = value.trim();
    if (!q) return;
    setSuggestions(null);
    setTab("all");
    navigate(`/search?q=${encodeURIComponent(q)}`);
  };

  const reuse = (value: string) => {
    setDraft(value);
    submit(value);
  };

  const clearHistory = () => {
    clearSearchHistory();
    setHistory(readSearchHistory());
  };

  const showCities = tab !== "attraction";
  const showAttractions = tab !== "city";
  const hasResults = cities.length > 0 || attractions.length > 0;

  return (
    <div className="searchPage">
      <BackBar to="/" />

      <form
        className="searchBox"
        onSubmit={(event) => {
          event.preventDefault();
          submit(draft);
        }}
      >
        <input
          className="searchInput"
          value={draft}
          placeholder="搜城市或景点，例如：北京 / 故宫"
          onChange={(event) => setDraft(event.target.value)}
          aria-label="搜索关键词"
        />
        <button className="btn btnPrimary searchSubmit" type="submit">
          搜索
        </button>
        {suggestions && (suggestions.cities.length > 0 || suggestions.attractions.length > 0) && (
          <div className="searchSuggest">
            {suggestions.cities.length > 0 && (
              <div className="searchSuggestGroup">
                <span className="searchSuggestLabel">城市</span>
                <div className="chipRow">
                  {suggestions.cities.map((city) => (
                    <button key={`city-${city.name}`} type="button" className="chip" onClick={() => reuse(city.name)}>
                      {tagEmoji(city.tag)} {city.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {suggestions.attractions.length > 0 && (
              <div className="searchSuggestGroup">
                <span className="searchSuggestLabel">景点</span>
                <div className="chipRow">
                  {suggestions.attractions.map((item) => (
                    <button
                      key={`attraction-${item.city}-${item.name}`}
                      type="button"
                      className="chip"
                      onClick={() => reuse(item.name)}
                    >
                      {tagEmoji(item.tags[0] ?? "")} {item.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </form>

      {history.length > 0 && !keyword && (
        <section className="searchHistory">
          <div className="searchSectionHead">
            <span className="searchSectionTitle">最近搜索</span>
            <button type="button" className="searchClearBtn" onClick={clearHistory}>
              清空
            </button>
          </div>
          <div className="chipRow">
            {history.map((item) => (
              <button key={item} type="button" className="chip" onClick={() => reuse(item)}>
                {item}
              </button>
            ))}
          </div>
        </section>
      )}

      {error && (
        <p className="errorBar" role="alert">
          {error}
        </p>
      )}

      <div className="searchResultHead">
        <h1 className="searchResultTitle">{keyword ? `“${keyword}” 的结果` : "热门推荐"}</h1>
        <div className="searchTabs" role="tablist">
          {RESULT_TABS.map((item) => (
            <button
              key={item.value}
              type="button"
              role="tab"
              aria-selected={item.value === tab}
              className={item.value === tab ? "searchTab searchTabActive" : "searchTab"}
              onClick={() => setTab(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <Skeleton lines={5} />
      ) : (
        <>
          {showCities && cities.length > 0 && (
            <section>
              <h2 className="searchGroupTitle">城市</h2>
              <div className="gridCards">
                {cities.map((city) => (
                  <Link key={city.name} className="placeCard" to={`/city/${encodeURIComponent(city.name)}`}>
                    <span className="placeCardTitle">{city.name}</span>
                    <span className="placeCardMeta">
                      {city.province} · {city.tag}
                      {typeof city.attraction_count === "number" ? ` · ${city.attraction_count} 个景点` : ""}
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {showAttractions && sortedAttractions.length > 0 && (
            <section>
              <h2 className="searchGroupTitle">景点</h2>
              <div className="gridCards">
                {sortedAttractions.map((item) => (
                  <Link
                    key={`${item.city}-${item.name}`}
                    className="placeCard"
                    to={`/attraction/${encodeURIComponent(item.name)}`}
                  >
                    <PlaceImage src={item.image} name={item.name} city={item.city} />
                    <span className="placeCardTitle">{item.name}</span>
                    <span className="placeCardMeta">
                      {item.city} · {item.ticket_price === 0 ? "免费" : `${item.ticket_price} 元`}
                    </span>
                    {item.tags.length > 0 && (
                      <span className="chipRow">
                        {item.tags.map((tag) => (
                          <span key={tag} className="tagPill">
                            {tagEmoji(tag)} {tag}
                          </span>
                        ))}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            </section>
          )}

          {!error && !hasResults && (
            <EmptyState
              emoji="🔍"
              title={keyword ? "没有找到匹配的结果" : "暂无热门推荐"}
              hint={keyword ? "换一个城市名或景点关键词再试试。" : "先去首页逛逛热门城市吧。"}
            />
          )}
        </>
      )}
    </div>
  );
}