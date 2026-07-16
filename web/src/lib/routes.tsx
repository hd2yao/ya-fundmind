import {
  BookOpenCheck,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  FileText,
  LayoutDashboard,
  Newspaper,
  SearchCheck,
  Sparkles
} from "lucide-react";
import type { ComponentType } from "react";

export type NavigationItem = {
  path: string;
  label: string;
  description: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean }>;
};

export const NAVIGATION_ITEMS: NavigationItem[] = [
  { path: "/", label: "研究总览", description: "运行与质量", icon: LayoutDashboard },
  { path: "/market", label: "市场情报", description: "主题与趋势", icon: ChartNoAxesCombined },
  { path: "/funds", label: "自选研究", description: "基金与 ETF", icon: SearchCheck },
  { path: "/portfolio", label: "组合分析", description: "暴露与缺口", icon: BriefcaseBusiness },
  { path: "/news", label: "新闻证据", description: "新闻与公告", icon: Newspaper },
  { path: "/copilot", label: "研究助手", description: "证据化问答", icon: Sparkles },
  { path: "/review", label: "人工审核", description: "复核队列", icon: BookOpenCheck },
  { path: "/reports", label: "报告中心", description: "本地产物", icon: FileText }
];
