import { afterEach, expect, test, vi } from "vitest";
import { playSyncCue } from "./syncCue";
afterEach(() => vi.useRealTimers());
function audio() {
  return {
    volume: 0,
    onended: null as (() => void) | null,
    onerror: null as (() => void) | null,
    play: vi.fn().mockResolvedValue(undefined),
    pause: vi.fn(),
    load: vi.fn(),
    removeAttribute: vi.fn(),
  } as unknown as HTMLAudioElement;
}
test("reminder follows audio completion by two seconds", () => {
  vi.useFakeTimers();
  const a = audio(),
    ready = vi.fn();
  playSyncCue(true, 0.5, ready, () => a);
  vi.advanceTimersByTime(4000);
  expect(ready).not.toHaveBeenCalled();
  a.onended?.(new Event("ended"));
  vi.advanceTimersByTime(1999);
  expect(ready).not.toHaveBeenCalled();
  vi.advanceTimersByTime(1);
  expect(ready).toHaveBeenCalledTimes(1);
  expect(a.pause).toHaveBeenCalled();
});
test("cancel prevents stale reminders and frees the player", () => {
  vi.useFakeTimers();
  const a = audio(),
    ready = vi.fn();
  const stop = playSyncCue(true, 0.5, ready, () => a);
  stop();
  vi.advanceTimersByTime(30000);
  expect(ready).not.toHaveBeenCalled();
  expect(a.pause).toHaveBeenCalled();
  expect(a.onended).toBeNull();
});
test("muted and broken media still allow reminders", async () => {
  vi.useFakeTimers();
  const ready = vi.fn();
  playSyncCue(false, 0.5, ready);
  vi.advanceTimersByTime(2000);
  expect(ready).toHaveBeenCalledTimes(1);
  const a = audio();
  a.play = vi.fn().mockRejectedValue(new Error("blocked"));
  playSyncCue(true, 0.5, ready, () => a);
  await Promise.resolve();
  vi.advanceTimersByTime(2000);
  expect(ready).toHaveBeenCalledTimes(2);
});
test("stalled media is bounded and only acknowledges once", () => {
  vi.useFakeTimers();
  const ready = vi.fn(),
    a = audio();
  playSyncCue(true, 0.5, ready, () => a);
  vi.advanceTimersByTime(17000);
  expect(ready).toHaveBeenCalledTimes(1);
  vi.advanceTimersByTime(30000);
  expect(ready).toHaveBeenCalledTimes(1);
});
