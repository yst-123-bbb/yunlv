import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiPost, ApiError } from "../api/client";
import { sendChat } from "../api/catalog";
import type { ChatDraft } from "../api/catalog";
import { isAiReady, readAiConfig, readPrefs } from "../storage/localStore";

const AI_MISSING_TIP = "请先在「我的 → AI 接入」填写 API Key 后再制定计划";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const GREETING =
  "把你想要的旅行说给我听：想去哪、玩几天、从哪出发、几个人、预算多少，我会逐条和你确认，信息齐了就能一键生成行程。";

function draftSummary(draft: ChatDraft): string {
  const parts = [`${draft.departure || "出发地待定"} → ${draft.destination}`];
  if (draft.days) parts.push(`${draft.days} 天`);
  if (draft.people) parts.push(`${draft.people} 人`);
  if (draft.dep_date) parts.push(draft.dep_date);
  if (draft.budget) parts.push(`人均 ${draft.budget} 元`);
  return parts.join(" · ");
}

export default function PlanChatPage() {
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", content: GREETING }]);
  const [input, setInput] = useState("");
  const [draft, setDraft] = useState<ChatDraft | null>(null);
  const [sending, setSending] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);

  const aiFallback = !isAiReady() && readAiConfig().allow_local_fallback;

  useEffect(() => {
    const node = listRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, draft]);

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setSending(true);
    setError("");

    try {
      const result = await sendChat(next, { ...readPrefs() });
      setMessages([...next, { role: "assistant", content: result.reply }]);
      setDraft(result.draft);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setSending(false);
    }
  }

  async function handleGenerate() {
    if (!draft || generating) return;

    if (!isAiReady() && !readAiConfig().allow_local_fallback) {
      setBlocked(true);
      setError(AI_MISSING_TIP);
      return;
    }
    setBlocked(false);

    setGenerating(true);
    setError("");
    try {
      const result = await apiPost<{ session_id: string }>("/api/plan", { user_data: draft });
      navigate(`/plan/${encodeURIComponent(result.session_id)}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
      setGenerating(false);
    }
  }

  return (
    <section className="card planCard planChat">
      <header className="chatHeader">
        <h1 className="chatTitle">自由对话</h1>
        <p className="planHint">和助手聊需求，信息齐了即可生成行程</p>
      </header>

      {aiFallback ? <p className="muted">当前未接入 AI，将使用本地规则生成</p> : null}

      {error ? (
        <p className="errorBar" role="alert">
          {error}
        </p>
      ) : null}

      {blocked ? (
        <p>
          <button type="button" className="btn btnPrimary" onClick={() => navigate("/me/ai")}>
            前往「我的 → AI 接入」设置
          </button>
        </p>
      ) : null}

      <div className="chatList" ref={listRef}>
        {messages.map((message, index) => (
          <div
            key={index}
            className={
              message.role === "user" ? "chatBubble chatBubbleUser" : "chatBubble chatBubbleBot"
            }
          >
            {message.content}
          </div>
        ))}
        {sending ? <div className="chatBubble chatBubbleBot muted">正在思考…</div> : null}
      </div>

      <form className="chatInputRow" onSubmit={handleSend}>
        <input
          className="chatInput"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="例如：从北京出发去大理玩 4 天，两个人，人均 4000 元"
          aria-label="对话输入"
        />
        <button type="submit" className="btn btnPrimary chatSendBtn" disabled={sending || !input.trim()}>
          发送
        </button>
      </form>

      {draft ? (
        <div className="chatGenerateBar">
          <p className="muted">已收集需求：{draftSummary(draft)}</p>
          <button type="button" className="btn btnPrimary" onClick={handleGenerate} disabled={generating}>
            {generating ? "正在生成行程…" : "生成行程"}
          </button>
        </div>
      ) : null}
    </section>
  );
}