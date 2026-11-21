import { Link, useLocation, useNavigate } from "react-router-dom";

interface BackBarProps {
  to: string;
  label?: string;
}

/**
 * 顶部返回栏。
 * 站内跳转过来时优先回退到上一个页面（保留用户真实来路）；
 * 直接打开/刷新本页（无站内历史）时回退到 `to` 指定的兜底路由。
 */
export default function BackBar({ to, label = "返回" }: BackBarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const canGoBack = location.key !== "default";

  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (!canGoBack) return;
    event.preventDefault();
    navigate(-1);
  };

  return (
    <div className="backBar">
      <Link className="backBtn" to={to} onClick={handleClick}>← {label}</Link>
    </div>
  );
}