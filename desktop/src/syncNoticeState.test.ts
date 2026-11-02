import { test, expect } from "vitest";
import { syncNoticeState } from "./syncNoticeState";
test("progress is bounded and terminal results ignore late progress", () => {
  const start = syncNoticeState(null, { event: "sync-started" });
  const progress = syncNoticeState(start, {
    event: "sync-progress",
    message: "확인 중",
    current: 9,
    total: 4,
  });
  expect(progress?.current).toBe(4);
  const done = syncNoticeState(progress, {
    event: "sync-complete",
    stats: { new_courses: 2, new: 5, updated: 1 },
    warnings: [],
  });
  expect(done?.phase).toBe("success");
  expect(done?.stats.new_courses).toBe(2);
  expect(
    syncNoticeState(done, { event: "sync-progress", message: "late" }),
  ).toBe(done);
  expect(syncNoticeState(done, { event: "sync-started" })?.phase).toBe(
    "running",
  );
});
test("partial success exposes actionable errors and ignores invalid counts", () => {
  const state = syncNoticeState(null, {
    event: "sync-complete",
    stats: { new: NaN, new_courses: -1, updated: 3 },
    warnings: ["영상 확인 필요", null],
  });
  expect(state?.phase).toBe("warning");
  expect(state?.stats).toEqual({ updated: 3 });
  expect(state?.warnings).toEqual(["영상 확인 필요"]);
  expect(syncNoticeState(state, { event: "sync-cancelled" })?.phase).toBe(
    "cancelled",
  );
});
