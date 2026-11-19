import { useState } from "react";
import type { FormEvent } from "react";
import { apiPost } from "../api/client";

interface CorrectionFormProps {
  entityId?: number;
  fieldName?: string;
  onSubmitted?: () => void;
}

interface SubmitResponse {
  id: number;
}

function errorText(err: unknown): string {
  if (err && typeof err === "object" && "detail" in err) {
    const detail = (err as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return err instanceof Error ? err.message : String(err);
}

export default function CorrectionForm({ entityId, fieldName, onSubmitted }: CorrectionFormProps) {
  const [targetId, setTargetId] = useState(entityId === undefined ? "" : String(entityId));
  const [field, setField] = useState(fieldName ?? "");
  const [proposed, setProposed] = useState("");
  const [reason, setReason] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [acceptedId, setAcceptedId] = useState<number | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!field.trim() || !proposed.trim() || !reason.trim()) {
      setError("请填写字段名、建议值与纠错理由");
      return;
    }
    const parsedId = targetId.trim() ? Number(targetId.trim()) : null;
    if (parsedId !== null && !Number.isInteger(parsedId)) {
      setError("实体 ID 需为整数");
      return;
    }

    setPending(true);
    setError("");
    try {
      const res = await apiPost<SubmitResponse>("/api/review", {
        entity_id: parsedId,
        field_name: field.trim(),
        proposed_value: proposed.trim(),
        reason: reason.trim(),
        raw_excerpt: excerpt.trim() || null,
      });
      setAcceptedId(res.id);
      setProposed("");
      setReason("");
      setExcerpt("");
      onSubmitted?.();
    } catch (err) {
      setAcceptedId(null);
      setError(`提交失败：${errorText(err)}`);
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2 className="cardTitle">发现信息有误？告诉我们</h2>
      {error && (
        <p className="errorBar" role="alert">
          {error}
        </p>
      )}
      {acceptedId !== null && (
        <p className="muted" role="status">
          已提交，等待人工审核（受理编号 {acceptedId}），审核通过后会更新资料。
        </p>
      )}
      <div className="formGrid">
        <label className="field">
          实体 ID（可选）
          <input
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            inputMode="numeric"
            placeholder="不填则由审核员定位"
          />
        </label>
        <label className="field">
          字段名
          <input
            value={field}
            onChange={(e) => setField(e.target.value)}
            placeholder="如 open_time / avg_price"
            required
          />
        </label>
        <label className="field fieldWide">
          建议值
          <input
            value={proposed}
            onChange={(e) => setProposed(e.target.value)}
            placeholder="你看到的正确内容"
            required
          />
        </label>
        <label className="field fieldWide">
          纠错理由
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="如：景区官网显示周一闭馆"
            required
          />
        </label>
        <label className="field fieldWide">
          原文摘录（可选）
          <input
            value={excerpt}
            onChange={(e) => setExcerpt(e.target.value)}
            placeholder="官网/游记中的原句，便于核实"
          />
        </label>
      </div>
      <div style={{ marginTop: 16 }}>
        <button className="btn btnPrimary" type="submit" disabled={pending}>
          {pending ? "提交中…" : "提交纠错"}
        </button>
      </div>
    </form>
  );
}