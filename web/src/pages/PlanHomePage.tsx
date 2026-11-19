import { Link, Navigate, Outlet, useLocation } from "react-router-dom";

const MODES = [
  {
    to: "/plan/quick",
    icon: "⚡",
    title: "快速制定",
    desc: "填表 1 分钟，按天生成完整行程",
    cta: "去填写 →",
  },
  {
    to: "/plan/chat",
    icon: "💬",
    title: "自由制定",
    desc: "和助手聊需求，随时调整",
    cta: "开始对话 →",
  },
];

export default function PlanHomePage() {
  const { pathname } = useLocation();

  // 直接访问 /plan 时落到快速制定，避免出现只有伸缩栏没有内容的空壳页面
  if (pathname === "/plan" || pathname === "/plan/") {
    return <Navigate to="/plan/quick" replace />;
  }

  return (
    <>
      <header className="heroBanner">
        <h2 className="heroTitle">制定计划</h2>
        <p className="heroSub">选择快速制定按表单填写，或用自由制定边聊边梳理需求。</p>
      </header>

      <div className="modeCards">
        {MODES.map((mode) => {
          const active = pathname.endsWith(mode.to);
          return (
            <Link
              key={mode.to}
              to={mode.to}
              className={"modeCard" + (active ? " modeCardActive" : "")}
            >
              <span className="modeIcon" aria-hidden="true">
                {mode.icon}
              </span>
              <span className="modeTitle">{mode.title}</span>
              <span className="modeDesc">{mode.desc}</span>
              <span className="modeCta">{mode.cta}</span>
            </Link>
          );
        })}
      </div>

      <Outlet />
    </>
  );
}