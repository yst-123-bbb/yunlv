import { useEffect, useState } from "react";
import { apiPost } from "../api/client";
import type { Issue, ItineraryDay, PlanSession } from "../api/client";

interface ItineraryEditorProps {
  sessionId: string;
  itinerary: ItineraryDay[];
  onStateChange: (state: PlanSession) => void;
}

interface ModifyResponse {
  state: PlanSession;
  issues: Issue[];
}

interface DragSource {
  day: number;
  index: number;
}

function errorText(err: unknown): string {
  if (err && typeof err === "object" && "detail" in err) {
    const detail = (err as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return err instanceof Error ? err.message : String(err);
}

export default function ItineraryEditor({
  sessionId,
  itinerary,
  onStateChange,
}: ItineraryEditorProps) {
  const [days, setDays] = useState<ItineraryDay[]>(itinerary);
  const [dragSource, setDragSource] = useState<DragSource | null>(null);
  const [overKey, setOverKey] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);

  useEffect(() => {
    setDays(itinerary);
  }, [itinerary]);

  async function commitReorder(day: number, before: ItineraryDay[], reordered: ItineraryDay[]) {
    const target = reordered.find((d) => d.day === day);
    if (!target) return;

    setDays(reordered);
    setPending(true);
    setError(null);
    try {
      const res = await apiPost<ModifyResponse>(`/api/plan/${sessionId}/modify`, {
        day,
        reorder: target.items.map((item) => item.name),
      });
      setIssues(res.issues ?? []);
      onStateChange(res.state);
    } catch (err) {
      setDays(before);
      setError(`排序保存失败：${errorText(err)}`);
    } finally {
      setPending(false);
      setDragSource(null);
      setOverKey(null);
    }
  }

  function handleDrop(dayIndex: number, toIndex: number) {
    if (!dragSource || pending) return;
    if (dragSource.day !== dayIndex || dragSource.index === toIndex) {
      setDragSource(null);
      setOverKey(null);
      return;
    }

    const source = days[dayIndex];
    if (!source) return;
    const items = [...source.items];
    const [moved] = items.splice(dragSource.index, 1);
    if (!moved) return;
    items.splice(toIndex, 0, moved);

    const reordered = days.map((d, i) => (i === dayIndex ? { ...d, items } : d));
    void commitReorder(source.day, days, reordered);
  }

  if (days.length === 0) {
    return (
      <section className="card">
        <h2 className="cardTitle">行程编辑</h2>
        <p className="muted">暂无行程，完成方案选择后可在此调整每日顺序。</p>
      </section>
    );
  }

  return (
    <section className="card">
      <h2 className="cardTitle">行程编辑</h2>
      <p className="muted">拖动同一天内的条目可调整游玩顺序，松手后自动保存。</p>

      {error && <div className="errorBar">{error}</div>}

      {days.map((day, dayIndex) => (
        <div key={day.day} style={{ marginTop: 16 }}>
          <h3 style={{ fontSize: 15, marginBottom: 8 }}>
            第 {day.day} 天 · {day.date}
          </h3>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {day.items.map((item, index) => {
              const key = `${day.day}-${index}`;
              const isOver = overKey === key && dragSource?.day === dayIndex;
              const isDragging = dragSource?.day === dayIndex && dragSource.index === index;
              return (
                <li
                  key={key}
                  draggable={!pending}
                  onDragStart={() => {
                    setDragSource({ day: dayIndex, index });
                    setError(null);
                  }}
                  onDragOver={(event) => {
                    if (!dragSource || dragSource.day !== dayIndex) return;
                    event.preventDefault();
                    setOverKey(key);
                  }}
                  onDragLeave={() => {
                    setOverKey((current) => (current === key ? null : current));
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    handleDrop(dayIndex, index);
                  }}
                  onDragEnd={() => {
                    setDragSource(null);
                    setOverKey(null);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 10px",
                    marginBottom: 6,
                    borderRadius: "var(--radius)",
                    border: `1px solid ${isOver ? "var(--accent)" : "transparent"}`,
                    background: "rgba(127, 127, 127, 0.08)",
                    cursor: pending ? "progress" : "grab",
                    opacity: isDragging ? 0.4 : 1,
                  }}
                >
                  <span className="muted" aria-hidden="true">
                    ⋮⋮
                  </span>
                  <span style={{ flex: 1 }}>{item.name}</span>
                  {item.start && (
                    <span className="muted">
                      {item.start}
                      {item.end ? `–${item.end}` : ""}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}

      {issues.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h3 style={{ fontSize: 15, marginBottom: 8 }}>行程提示</h3>
          <ul className="muted" style={{ margin: 0, paddingLeft: 20 }}>
            {issues.map((issue, index) => (
              <li key={`${issue.code ?? "issue"}-${index}`}>
                {typeof issue.day === "number" ? `第 ${issue.day} 天：` : ""}
                {typeof issue.message === "string" && issue.message
                  ? issue.message
                  : String(issue.code ?? "未知提示")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}