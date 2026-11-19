import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

const iconProps = {
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

const NAV_ITEMS: { to: string; label: string; icon: ReactNode }[] = [
  {
    to: "/",
    label: "首页",
    icon: (
      <svg {...iconProps} aria-hidden="true">
        <path d="M3 10.5 12 3l9 7.5" />
        <path d="M5.5 9.5V21h13V9.5" />
      </svg>
    ),
  },
  {
    to: "/plan",
    label: "制定计划",
    icon: (
      <svg {...iconProps} aria-hidden="true">
        <rect x="3" y="4" width="18" height="17" rx="2" />
        <path d="M8 2v4M16 2v4M3 10h18" />
      </svg>
    ),
  },
  {
    to: "/me",
    label: "我的",
    icon: (
      <svg {...iconProps} aria-hidden="true">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
      </svg>
    ),
  },
];

export default function BottomNav() {
  const { pathname } = useLocation();

  const isActive = (to: string): boolean => {
    if (to === "/") return pathname === "/";
    if (to === "/plan") return pathname === "/plan" || pathname.startsWith("/plan/");
    return pathname === to;
  };

  return (
    <nav className="bottomNav">
      {NAV_ITEMS.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className={isActive(item.to) ? "bottomNavItem bottomNavItemActive" : "bottomNavItem"}
        >
          {item.icon}
          {item.label}
        </Link>
      ))}
    </nav>
  );
}