import { expect, test } from "vitest";
import { matchesEventFilter } from "./eventFilters";
import type { EventItem } from "./types";
test("기한 경계, 완료 항목과 기한 없는 항목을 구분한다", () => {
  const now = Date.parse("2026-11-01T12:00:00+09:00");
  const event = (completed: boolean, due_at: string | null) =>
    ({ completed, due_at }) as EventItem;
  const late = event(false, "2026-11-01T12:00:00+09:00");
  expect(matchesEventFilter(late, "overdue", now)).toBe(true);
  expect(matchesEventFilter(late, "pending", now)).toBe(true);
  expect(matchesEventFilter(late, "done", now)).toBe(false);
  expect(matchesEventFilter(event(true, late.due_at), "overdue", now)).toBe(
    false,
  );
  expect(matchesEventFilter(event(true, late.due_at), "done", now)).toBe(true);
  expect(matchesEventFilter(event(false, null), "pending", now)).toBe(true);
  expect(matchesEventFilter(event(false, null), "overdue", now)).toBe(false);
  expect(
    matchesEventFilter(
      event(false, "2026-11-01T12:00:01+09:00"),
      "overdue",
      now,
    ),
  ).toBe(false);
});
