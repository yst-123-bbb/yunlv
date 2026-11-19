import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { fetchTransfers } from "../api/transfer";
import type { TransferLeg, TransferResult } from "../api/transfer";
import EmptyState from "./EmptyState";
import Skeleton from "./Skeleton";

const MODE_LABEL: Record<TransferLeg["mode"], string> = { train: "高铁", flight: "飞机" };

export default function TransferPanel({
  origin,
  dest,
  people = 1,
}: {
  origin: string;
  dest: string;
  people?: number;
}) {
  const [result, setResult] = useState<TransferResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const enabled = Boolean(origin && dest && origin !== dest);

  useEffect(() => {
    if (!enabled) {
      setResult(null);
      setError("");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    setResult(null);
    fetchTransfers(origin, dest, people)
      .then((res) => {
        if (!cancelled) setResult(res);
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
  }, [origin, dest, people, enabled]);

  return (
    <div>
      <p className="muted">价格为估算，非实时报价</p>
      {!enabled ? <p className="muted">缺少出发地或目的地，无法比较中转方案</p> : null}
      {enabled && loading ? <Skeleton lines={3} /> : null}
      {enabled && !loading && error ? (
        <p className="errorBar" role="alert">
          {error}
        </p>
      ) : null}
      {enabled && !loading && !error && result ? (
        <>
          <p className="muted">
            直达最低 {result.direct.total} 元/人 · {result.direct.duration_min} 分钟 · {result.people} 人合计约{" "}
            {Math.round(result.direct.total * result.people)} 元
          </p>
          {result.options.length === 0 ? (
            <>
              <EmptyState title="暂无更便宜的中转组合" hint={result.note} />
              {result.best ? (
                <p className="muted">
                  最便宜中转：{result.best.summary}，{result.best.total} 元，比直达多{" "}
                  {result.best.total - result.direct.total * result.people} 元
                </p>
              ) : null}
            </>
          ) : (
            <div className="gridCards">
              {result.options.map((option) => (
                <div className="transferCard" key={option.via}>
                  <div className="cardTitle">{option.summary}</div>
                  <div className="transferLegs">
                    {option.legs.map((leg, index) => (
                      <span key={index}>
                        {MODE_LABEL[leg.mode]} {leg.from}→{leg.to} {leg.price} 元 · {leg.duration_min} 分钟
                      </span>
                    ))}
                  </div>
                  <div>
                    总价 {option.total} 元 ·{" "}
                    <span className="transferSave">节省 {option.save} 元</span>
                  </div>
                  <p className="muted">
                    {option.via}（{option.via_province}）中转 · 全程 {option.duration_min} 分钟
                  </p>
                </div>
              ))}
            </div>
          )}
          <p className="muted">{result.note}</p>
        </>
      ) : null}
    </div>
  );
}