import { expect, test } from "vitest";
import { focusSeconds, timerText, type FocusState } from "./focusState";
const state: FocusState = {
  running: true,
  mode: "pomodoro",
  phase: "focus",
  round: 0,
  elapsed: 30,
  duration: 1500,
  work: 25,
  short: 5,
  long: 15,
  finished: false,
};
test("timer uses elapsed time instead of number of ticks", () => {
  expect(focusSeconds(state, 120000)).toBe(1350);
  expect(focusSeconds(state, 2000000)).toBe(0);
  expect(focusSeconds({ ...state, running: false }, 120000)).toBe(1470);
  expect(focusSeconds({ ...state, mode: "free" }, 120000)).toBe(150);
  expect(timerText(1350)).toBe("22:30");
});
