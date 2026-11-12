import type { Level } from "./types";

export const LEVEL_LABEL: Record<string, string> = {
  weak: "薄弱",
  medium: "熟悉中",
  mastered: "已掌握",
  fluent: "熟练",
};

export const RELATION_LABEL: Record<string, string> = {
  prerequisite: "前置",
  related: "相关",
  part_of: "属于",
};

export const REVIEW_STATUS: Record<string, string> = {
  overdue: "已逾期",
  today: "今天到期",
  upcoming: "即将复习",
  unscheduled: "未排期",
};

export function formatWhen(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatDay(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "numeric",
    day: "numeric",
  }).format(date);
}

export function formatScore(value?: number | null): string {
  if (value == null) return "—";
  return value.toFixed(1);
}

export function scoreTone(value?: number | null): string {
  if (value == null) return "";
  if (value >= 75) return "good";
  if (value >= 55) return "warn";
  return "bad";
}

export function levelTone(level?: Level | null): string {
  return level ?? "none";
}
