import type { EventItem } from "./types";
export type EventFilter = "all" | "pending" | "done" | "overdue";
export function matchesEventFilter(
  event: EventItem,
  filter: EventFilter,
  now = Date.now(),
) {
  if (filter === "all") return true;
  if (filter === "done") return event.completed;
  if (filter === "pending") return !event.completed;
  return (
    !event.completed &&
    !!event.due_at &&
    new Date(event.due_at).getTime() <= now
  );
}
