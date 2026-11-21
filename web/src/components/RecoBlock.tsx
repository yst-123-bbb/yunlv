import { useEffect, useState } from "react";
import { fetchAttractionReco, fetchCityReco } from "../api/reco";
import type { RecoResult } from "../api/reco";

const COLLAPSE_THRESHOLD = 360;
const COLLAPSED_LINES = 8;

interface RecoBlockProps {
  kind: "attraction" | "city";
  name: string;
}

function fallbackUrl(name: string): string {
  return "https://www.xiaohongshu.com/search_result?keyword=" + encodeURIComponent(`${name} 攻略`);
}

export default function RecoBlock({ kind, name }: RecoBlockProps) {
  const [data, setData] = useState<RecoResult | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setData(null);
    setExpanded(false);

    const load = kind === "attraction" ? fetchAttractionReco : fetchCityReco;
    load(name)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("failed");
      });

    return () => {
      cancelled = true;
    };
  }, [kind, name]);

  const keyword = data?.keyword ?? `${name} 攻略`;
  const href = data?.search_url || fallbackUrl(name);

  const blurb = data?.blurb ?? "";
  const collapsible = blurb.length > COLLAPSE_THRESHOLD;
  const visibleBlurb = collapsible && !expanded ? `${blurb.split("\n").slice(0, COLLAPSED_LINES).join("\n")}…` : blurb;

  return (
    <section className="card">
      <h2 className="cardTitle">📕 小红书攻略</h2>
      {status === "loading" && <p className="muted">正在整理攻略…</p>}
      {status === "ready" && data && (
        <>
          <div className="recoBody">{visibleBlurb}</div>
          {collapsible && (
            <button type="button" className="recoToggle" onClick={() => setExpanded((prev) => !prev)}>
              {expanded ? "收起" : "展开全文"}
            </button>
          )}
        </>
      )}
      {status !== "loading" && (
        <>
          <a className="btn btnGhost" href={href} target="_blank" rel="noreferrer">
            在小红书搜「{keyword}」
          </a>
          <p className="muted">以上为本站基于公开信息的整理，最新的实拍与排队情况请点下方链接查看。</p>
        </>
      )}
    </section>
  );
}