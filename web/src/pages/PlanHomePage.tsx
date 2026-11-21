import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import BackBar from "../components/BackBar";

export default function PlanHomePage() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  // 直接访问 /plan 时落到快速制定，避免出现只有伸缩栏没有内容的空壳页面
  if (pathname === "/plan" || pathname === "/plan/") {
    return <Navigate to="/plan/quick" replace />;
  }

  const isChat = pathname.endsWith("/plan/chat");

  return (
    <div className="planNarrow">
      <div className="planModeBar">
        <BackBar to="/" />
        <div className="modeSwitch" role="tablist" aria-label="制定方式" data-active={isChat ? "chat" : "quick"}>
          <span className="modeSwitchThumb" aria-hidden="true" />
          <button
            type="button"
            role="tab"
            aria-selected={!isChat}
            className={isChat ? "modeSwitchItem" : "modeSwitchItem modeSwitchItemActive"}
            onClick={() => navigate("/plan/quick")}
          >
            模式
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isChat}
            className={isChat ? "modeSwitchItem modeSwitchItemActive" : "modeSwitchItem"}
            onClick={() => navigate("/plan/chat")}
          >
            自由模式对话
          </button>
        </div>
      </div>
      <Outlet />
    </div>
  );
}