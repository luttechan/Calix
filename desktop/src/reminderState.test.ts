import { expect, test } from "vitest";
import { acceptReminder, type ReminderEnvelope } from "./reminderState";
const empty: ReminderEnvelope = { revision: 2, payload: null };
test("late initial reads cannot resurrect a closed reminder", () => {
  expect(acceptReminder(empty, { revision: 1, payload: {} as never })).toBe(
    empty,
  );
});
test("close state wins and new alerts can reopen", () => {
  const shown = { revision: 3, payload: {} as never };
  expect(acceptReminder(empty, shown)).toBe(shown);
  const closed = { revision: 4, payload: null };
  expect(acceptReminder(shown, closed)).toBe(closed);
  expect(acceptReminder(closed, shown)).toBe(closed);
});
test.each([NaN, Infinity, -1, 3.5])(
  "invalid revision %s is ignored",
  (revision) => {
    expect(acceptReminder(empty, { revision, payload: null })).toBe(empty);
  },
);
