export const PLAN_STAGES: string[] = [
  "整理出行需求",
  "查询高铁与航班",
  "筛选沿线景点",
  "编排每日行程",
  "核算预算",
  "完成",
];

interface PlanProgressProps {
  stage: number;
  error?: string;
  waitedSeconds?: number;
  onRetry?: () => void;
  retrying?: boolean;
}

export default function PlanProgress({
  stage,
  error,
  waitedSeconds,
  onRetry,
  retrying = false,
}: PlanProgressProps) {
  const done = Math.min(Math.max(stage, 0), 6);

  if (error) {
    return (
      <div className="progressPanel">
        <h2 className="cardTitle">正在为你制定行程</h2>
        <p className="errorBar" role="alert">
          {error}
        </p>
        {onRetry && (
          <button type="button" className="btn btnPrimary" onClick={onRetry} disabled={retrying}>
            {retrying ? "重试中…" : "重新生成"}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="progressPanel">
      <h2 className="cardTitle">正在为你制定行程</h2>
      <div className="progressBar">
        <div
          className="progressBarFill"
          style={{ width: `${Math.max(6, Math.round((done / 6) * 100))}%` }}
        />
      </div>
      <ol className="progressSteps">
        {PLAN_STAGES.map((label, i) => {
          const className =
            "progressStep" +
            (i < done ? " progressStepDone" : "") +
            (i === done ? " progressStepActive" : "");
          return (
            <li key={label} className={className}>
              {label}
            </li>
          );
        })}
      </ol>
      <div className="progressMeta">
        已完成 {done}/6 步
        {waitedSeconds !== undefined && waitedSeconds !== null ? `，已等待 ${waitedSeconds} 秒` : ""}
      </div>
    </div>
  );
}