import { dateKey } from "./dates";
import type { EventItem } from "./types";

export type CalendarRange = { start: string; end: string };
export type CalendarPeriod = CalendarRange & { event: EventItem };

export function orderedRange(a: string, b: string): CalendarRange {
  return a <= b ? { start: a, end: b } : { start: b, end: a };
}

export function dayDistance(from: string, to: string): number {
  return (Date.parse(to) - Date.parse(from)) / 86400000;
}

export function shiftCalendarDay(day: string, offset: number): string {
  return new Date(Date.parse(day) + offset * 86400000).toISOString().slice(0, 10);
}

export function calendarPeriod(event: EventItem): CalendarPeriod | null {
  if (!event.manual || !event.start_at || !event.due_at) return null;
  const start = dateKey(event.start_at);
  const end = dateKey(event.due_at);
  return start < end ? { start, end, event } : null;
}

export function layoutCalendarWeek(days: string[], periods: CalendarPeriod[]) {
  const [first] = days;
  const last = days[days.length - 1];
  const segments: (CalendarPeriod & { from: number; to: number; lane: number })[] = [];
  const laneEnds: number[] = [];
  const hidden = days.map(() => 0);
  for (const period of periods) {
    if (period.end < first || period.start > last) continue;
    const from = period.start <= first ? 0 : days.indexOf(period.start);
    const to = period.end >= last ? days.length - 1 : days.indexOf(period.end);
    let lane = laneEnds.findIndex(end => end < from);
    if (lane < 0) lane = laneEnds.length;
    if (lane === 3) {
      for (let day = from; day <= to; day++) hidden[day]++;
      continue;
    }
    laneEnds[lane] = to;
    segments.push({ ...period, from, to, lane });
  }
  return { segments, lanes: laneEnds.length, hidden };
}
