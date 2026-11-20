import type { EventItem } from "./types";
export function deadlineGroup(event: EventItem, now: Date): string {
  if (event.completed) return "completed";
  const due = event.due_at ? new Date(event.due_at) : null;
  if (!due || !Number.isFinite(due.getTime())) return "undated";
  if (due.getTime() < now.getTime()) return "overdue";
  const end = new Date(now);
  end.setHours(24, 0, 0, 0);
  if (due < end) return "today";
  const limit = new Date(now);
  limit.setDate(limit.getDate() + 7);
  return due <= limit ? "week" : "later";
}
export function orderByDeadline(events: EventItem[]) {
  const time = (e: EventItem) => {
    const value = Date.parse(e.due_at || "");
    return Number.isFinite(value) ? value : Infinity;
  };
  return [...events].sort(
    (a, b) => time(a) - time(b) || a.title.localeCompare(b.title, "ko"),
  );
}
