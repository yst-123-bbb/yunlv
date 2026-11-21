import { useCallback, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../api/client";
import {
  AI_DEFAULT_CONFIG,
  clearAiConfig,
  maskApiKey,
  readAiConfig,
  writeAiConfig,
} from "../storage/localStore";
import type { AiConfig } from "../storage/localStore";
import Toast from "../components/Toast";
import BackBar from "../components/BackBar";

interface PingResult {
  ok: boolean;
  provider: string;
  model: string;
  message: string;
}

export default function AiSettingsPage() {
  const [config, setConfig] = useState<AiConfig>(() => readAiConfig());
  const [showKey, setShowKey] = useState(false);
  const [pinging, setPinging] = useState(false);
  const [pingResult, setPingResult] = useState<PingResult | null>(null);
  const [toast, setToast] = useState("");
  const closeToast = useCallback(() => setToast(""), []);

  const ready = config.api_key.trim().length > 0;

  function patch(next: Partial<AiConfig>) {
    setConfig((prev) => ({ ...prev, ...next }));
  }

  function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const saved = writeAiConfig({
      base_url: config.base_url.trim() || AI_DEFAULT_CONFIG.base_url,
      api_key: config.api_key.trim(),
      model: config.model.trim() || AI_DEFAULT_CONFIG.model,
      allow_local_fallback: config.allow_local_fallback,
    });
    setConfig(saved);
    setToast("AI 配置已保存到本浏览器");
  }

  async function handlePing() {
    setPinging(true);
    setPingResult(null);
    try {
      const result = await apiPost<PingResult>("/api/ai/ping", {});
      setPingResult(result);
    } catch (err) {
      setPingResult({
        ok: false,
        provider: "custom",
        model: config.model,
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setPinging(false);
    }
  }

  function handleClear() {
    clearAiConfig();
    setConfig(readAiConfig());
    setPingResult(null);
    setToast("已清除 AI 配置");
  }

  return (
    <>
      <BackBar to="/me" />
      <header className="pageHeader">
        <h2>AI 接入</h2>
      </header>

      <section className="card">
        <h2 className="cardTitle">当前状态</h2>
        <p className={ready ? "placeCardMeta" : "muted"}>
          {ready
            ? `已接入 · 模型 ${config.model || AI_DEFAULT_CONFIG.model} · Key ${maskApiKey(config.api_key)}`
            : "未接入 · 制定计划前需要填写 API Key，或开启下方「允许本地规则降级」"}
        </p>
        <p className="muted">Key 只保存在当前浏览器的 localStorage，不会上传到服务器存储，也不会写入日志。</p>
      </section>

      <section className="card">
        <h2 className="cardTitle">连接参数</h2>
        <form className="prefForm" onSubmit={handleSave}>
          <label className="field">
            <span>Base URL</span>
            <input
              type="url"
              value={config.base_url}
              placeholder={AI_DEFAULT_CONFIG.base_url}
              onChange={(event) => patch({ base_url: event.target.value })}
            />
          </label>

          <label className="field">
            <span>API Key</span>
            <input
              type={showKey ? "text" : "password"}
              value={config.api_key}
              placeholder="sk-..."
              autoComplete="off"
              onChange={(event) => patch({ api_key: event.target.value })}
            />
          </label>

          <div className="chipRow">
            <button
              className="btn btnGhost"
              type="button"
              onClick={() => setShowKey((prev) => !prev)}
              aria-pressed={showKey}
            >
              {showKey ? "隐藏 Key" : "显示 Key"}
            </button>
          </div>

          <label className="field">
            <span>模型名</span>
            <input
              type="text"
              value={config.model}
              placeholder={AI_DEFAULT_CONFIG.model}
              onChange={(event) => patch({ model: event.target.value })}
            />
          </label>

          <label className="field">
            <span>允许本地规则降级</span>
            <input
              type="checkbox"
              checked={config.allow_local_fallback}
              onChange={(event) => patch({ allow_local_fallback: event.target.checked })}
            />
            <span className="muted">开启后，未填写 Key 也可以生成计划，页面会标注为本地规则生成。</span>
          </label>

          <div className="chipRow">
            <button className="btn btnPrimary" type="submit">
              保存
            </button>
            <button className="btn" type="button" onClick={handlePing} disabled={pinging}>
              {pinging ? "测试中…" : "测试连接"}
            </button>
            <button className="btn btnGhost" type="button" onClick={handleClear}>
              清除配置
            </button>
          </div>
          <p className="muted">测试连接使用已保存的配置，修改参数后请先保存。</p>

          {pingResult && (
            <p className={pingResult.ok ? "placeCardMeta" : "errorBar"} role="status">
              {pingResult.ok ? "连接成功" : "连接失败"}：{pingResult.message}
            </p>
          )}
        </form>
      </section>

      <div className="chipRow">
        <Link className="btn btnGhost" to="/me">
          返回我的
        </Link>
      </div>

      <Toast message={toast} onClose={closeToast} tone="success" />
    </>
  );
}