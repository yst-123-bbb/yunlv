import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";

interface ReviewItem {
  id: number;
  entity_id: number | null;
  field_name: string;
  proposed_value: unknown;
  current_value: unknown;
  reason: string;
  status: string;
  created_at: string;
}

type ReviewAction = "approve" | "reject" | "merge";

const ACTION_LABELS: { action: ReviewAction; label: string; primary?: boolean }[] = [
  { action: "approve", label: "通过", primary: true },
  { action: "reject", label: "驳回" },
  { action: "merge", label: "合并" },
];

function errorText(err: unknown): string {
  if (err && typeof err === "object" && "detail" in err) {
    const detail = (err as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return err instanceof Error ? err.message : String(err);
}

function showValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export default function ReviewAdminPage() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiGet<{ items: ReviewItem[] }>("/api/review?status=pending");
      setItems(res.items ?? []);
      setError("");
    } catch (err) {
      setError(`加载待审列表失败：${errorText(err)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(itemId: number, action: ReviewAction) {
    setBusyId(itemId);
    setError("");
    try {
      await apiPost<{ ok: boolean }>(`/api/review/${itemId}/decide`, {
        action,
        note: (notes[itemId] ?? "").trim(),
      });
      await load();
    } catch (err) {
      setError(`审核操作失败：${errorText(err)}`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="planLayout">
      <section className="card">
        <h2 className="cardTitle">待审纠错（{items.length}）</h2>
        {error && (
          <p className="errorBar" role="alert">
            {error}
          </p>
        )}
        <div style={{ marginBottom: 16 }}>
          <button className="btn btnGhost" type="button" onClick={() => void load()} disabled={loading}>
            {loading ? "刷新中…" : "刷新"}
          </button>
        </div>
        {!loading && items.length === 0 && <p className="muted">暂无待审项</p>}
        {items.map((item) => (
          <article
            key={item.id}
            style={{
              borderTop: "1px solid var(--border)",
              padding: "16px 0",
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <div className="summary">
              <span>#{item.id}</span>
              <span>字段：{item.field_name}</span>
              <span>实体：{item.entity_id ?? "未关联"}</span>
              <span>提交于：{item.created_at}</span>
            </div>
            <div>
              <span className="muted">当前值：</span>
              <span>{showValue(item.current_value)}</span>
            </div>
            <div>
              <span className="muted">建议值：</span>
              <strong>{showValue(item.proposed_value)}</strong>
            </div>
            <div>
              <span className="muted">理由：</span>
              <span>{item.reason}</span>
            </div>
            <label className="field">
              审核备注
              <input
                value={notes[item.id] ?? ""}
                onChange={(e) => setNotes((prev) => ({ ...prev, [item.id]: e.target.value }))}
                placeholder="选填，合并时记录说明"
              />
            </label>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {ACTION_LABELS.map(({ action, label, primary }) => (
                <button
                  key={action}
                  className={primary ? "btn btnPrimary" : "btn btnGhost"}
                  type="button"
                  disabled={busyId === item.id}
                  onClick={() => void decide(item.id, action)}
                >
                  {label}
                </button>
              ))}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}