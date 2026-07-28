import {
  BookOpenCheck,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  FileText,
  LayoutDashboard,
  Newspaper,
  SearchCheck,
  Sparkles,
  Star
} from "lucide-react";
import type { ComponentType } from "react";

export type NavigationItem = {
  path: string;
  label: string;
  description: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean }>;
};

export type NavigationGroup = {
  label: string;
  items: NavigationItem[];
};

export const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    label: "数据终端",
    items: [
      { path: "/market", label: "行情总览", description: "指数 · 板块 · 主题", icon: ChartNoAxesCombined },
      { path: "/funds", label: "基金终端", description: "全市场 · 历史", icon: SearchCheck },
      { path: "/watchlist", label: "自选", description: "观察基金 · 只读", icon: Star },
      { path: "/portfolio", label: "组合", description: "持仓 · 暴露 · 缺口", icon: BriefcaseBusiness }
    ]
  },
  {
    label: "研究工具",
    items: [
      { path: "/copilot", label: "研究助手", description: "证据化问答", icon: Sparkles },
      { path: "/review", label: "人工审核", description: "复核队列", icon: BookOpenCheck }
    ]
  },
  {
    label: "系统工具",
    items: [
      { path: "/status", label: "系统状态", description: "运行 · 资料 · 状态", icon: LayoutDashboard },
      { path: "/reports", label: "报告中心", description: "日报 · 周报 · 导出", icon: FileText }
    ]
  }
];

export const NAVIGATION_ITEMS = NAVIGATION_GROUPS.flatMap((group) => group.items);

// These routes remain directly addressable, but are not product navigation
// destinations until they have formal, displayable data.
const ROUTE_ONLY_ITEMS: NavigationItem[] = [
  { path: "/news", label: "研究证据", description: "公开资料核对", icon: Newspaper }
];

export function getNavigationItem(pathname: string) {
  return (
    [...NAVIGATION_ITEMS, ...ROUTE_ONLY_ITEMS].find((item) => item.path === pathname)
    || [...NAVIGATION_ITEMS, ...ROUTE_ONLY_ITEMS].find((item) => pathname.startsWith(`${item.path}/`))
    || NAVIGATION_ITEMS[0]
  );
}
