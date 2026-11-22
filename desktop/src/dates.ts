import type { EventItem } from "./types";
import { locale, t } from "./i18n";
export const weekdays = ["월", "화", "수", "목", "금", "토", "일"];
const dayFormatter = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const dueFormatters = new Map<string, Intl.DateTimeFormat>();

export function monthName(month: number) {
  return new Intl.DateTimeFormat(locale(), { month: "short", timeZone: "UTC" })
    .format(new Date(Date.UTC(2000, month - 1)));
}

export function monthTitle(year: string | number, month: string | number) {
  return new Intl.DateTimeFormat(locale(), { year: "numeric", month: "long", timeZone: "UTC" })
    .format(new Date(Date.UTC(Number(year), Number(month) - 1)));
}
export function dateKey(value: Date | string = new Date()): string {
  return dayFormatter.format(new Date(value));
}
export function monthGrid(month: string): string[] {
  const [year, m] = month.split("-").map(Number);
  const first = new Date(Date.UTC(year, m - 1, 1));
  first.setUTCDate(first.getUTCDate() - ((first.getUTCDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(first);
    d.setUTCDate(d.getUTCDate() + i);
    return d.toISOString().slice(0, 10);
  });
}
export function shiftMonth(month: string, step: number) {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1 + step, 1)).toISOString().slice(0, 7);
}
export function localInput(value: string | null) {
  return value
    ? new Date(new Date(value).getTime() + 9 * 3600000)
        .toISOString()
        .slice(0, 16)
    : "";
}
export function dueText(value: string | null) {
  if (!value) return t("기한 없음");
  const language = locale();
  let formatter = dueFormatters.get(language);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(language, {
      timeZone: "Asia/Seoul",
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    });
    dueFormatters.set(language, formatter);
  }
  return formatter.format(new Date(value));
}
export function isExcusedMovie(event: EventItem) {
  return event.kind === "movie" && event.lms_data?.attendance_status === "excused";
}
export function status(event: EventItem, now = Date.now()): string {
  if (isExcusedMovie(event)) return t("공결");
  if (!event.completion_verified && !event.manual)
    return t(event.kind === "movie" ? "시청 미확인" : "제출 미확인");
  if (event.kind === "movie" && event.lms_data?.attendance_status === "late")
    return t("지각 시청");
  if (event.kind === "assignment" && event.lms_data?.status) {
    const state = event.lms_data.status;
    if (state === "graded")
      return t(event.lms_data.late ? "채점 완료 (지각 제출)" : "채점 완료");
    if (state === "late") return t("지각 제출");
    if (state === "submitted") return t("제출 완료");
    if (state === "missing") return t("미제출");
  }
  if (event.completed) return t(event.kind === "movie" ? "시청 완료" : "완료");
  if (!event.due_at) return t("기한 없음");
  const diff = new Date(event.due_at).getTime() - now;
  if (diff <= 0) return t(event.kind === "assignment" ? "미완료" : "기한 경과");
  if (diff < 3600000) return t("{0}분 전", [Math.max(1, Math.ceil(diff / 60000))]);
  if (diff < 86400000) return t("{0}시간 전", [Math.ceil(diff / 3600000)]);
  return t("{0}일 전", [Math.max(1, Math.floor(diff / 86400000))]);
}
export function remaining(events: EventItem[], now = Date.now()) {
  return events.filter(
    (e) => !e.completed && (!e.due_at || new Date(e.due_at).getTime() > now),
  );
}
