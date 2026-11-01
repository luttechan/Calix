import type { EventItem } from "./types";

export function groupByCourse(events: EventItem[]) {
  const groups = new Map<
    number,
    { id: number; name: string; events: EventItem[] }
  >();
  for (const event of events) {
    let group = groups.get(event.course_id);
    if (!group) {
      group = {
        id: event.course_id,
        name: event.course_name || "개인 일정",
        events: [],
      };
      groups.set(event.course_id, group);
    }
    group.events.push(event);
  }
  return [...groups.values()].sort(
    (a, b) =>
      a.name.localeCompare(b.name, "ko", { numeric: true }) || a.id - b.id,
  );
}
