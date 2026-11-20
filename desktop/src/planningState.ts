import type { EventItem, Session } from "./types";
import { orderByDeadline, deadlineGroup } from "./overviewState";
export function studyPlan(
  events: EventItem[],
  now: Date,
  budget: number,
  minutes: number,
) {
  return orderByDeadline(
    events.filter((e) => !e.completed && deadlineGroup(e, now) !== "overdue"),
  ).slice(0, Math.floor(Math.max(0, budget) / Math.max(5, minutes)));
}
export function busyDates(events: EventItem[], now: Date) {
  const dates = new Map<string, EventItem[]>();
  for (const e of events) {
    if (e.completed || !e.due_at) continue;
    const d = new Date(e.due_at);
    if (!Number.isFinite(+d) || d < now) continue;
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    dates.set(key, [...(dates.get(key) || []), e]);
  }
  return [...dates]
    .filter(([, items]) => items.length >= 3)
    .sort((a, b) => a[0].localeCompare(b[0]));
}
export function freeSlots(
  sessions: Session[],
  offDays: number[],
  duration: number,
) {
  const minute = (text: string) => {
    const [h, m] = text.split(":").map(Number);
    return h * 60 + m;
  };
  const result: { day: number; start: number; end: number }[] = [];
  for (let day = 0; day < 7; day++) {
    const blocks = offDays.includes(day)
      ? []
      : sessions
          .filter((s) => s.day === day && !s.is_online)
          .map((s) => [
            Math.max(540, minute(s.start_time)),
            Math.min(1080, minute(s.end_time)),
          ])
          .filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b) && b > a)
          .sort((a, b) => a[0] - b[0]);
    let cursor = 540;
    for (const [start, end] of [...blocks, [1080, 1080]]) {
      if (start - cursor >= duration)
        result.push({ day, start: cursor, end: start });
      cursor = Math.max(cursor, end);
    }
  }
  return result;
}
export function sessionLanes(sessions: Session[]) {
  const output = new Map<number, { lane: number; count: number }>();
  for (let day = 0; day < 7; day++) {
    const rows = sessions
      .filter((s) => !s.is_online && s.day === day)
      .sort(
        (a, b) =>
          a.start_time.localeCompare(b.start_time) ||
          a.end_time.localeCompare(b.end_time) ||
          a.id - b.id,
      );
    let group: Session[] = [],
      end = "";
    const flush = () => {
      const ends: string[] = [];
      for (const row of group) {
        let lane = ends.findIndex((e) => e <= row.start_time);
        if (lane < 0) lane = ends.length;
        ends[lane] = row.end_time;
        output.set(row.id, { lane, count: 0 });
      }
      for (const row of group) output.get(row.id)!.count = ends.length;
      group = [];
    };
    for (const row of rows) {
      if (group.length && row.start_time >= end) flush();
      group.push(row);
      end =
        group.length === 1
          ? row.end_time
          : row.end_time > end
            ? row.end_time
            : end;
    }
    flush();
  }
  return output;
}
