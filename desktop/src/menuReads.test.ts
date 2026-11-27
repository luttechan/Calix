import { beforeEach, expect, it, vi } from "vitest";
import { rpc } from "./bridge";
import { invalidateMenuReads, peekMenuRead, readMenu, rememberMenuRead } from "./menuReads";

vi.mock("./bridge", () => ({ rpc: vi.fn() }));
const call = vi.mocked(rpc);

beforeEach(() => {
  call.mockReset();
  invalidateMenuReads();
});

it("shares a request and reuses the stored rows on a later visit", async () => {
  const attendance = [{ key: "first" }];
  call.mockResolvedValueOnce(attendance);
  const first = readMenu("attendance.read");
  expect(readMenu("attendance.read")).toBe(first);
  await expect(first).resolves.toBe(attendance);
  expect(peekMenuRead("attendance.read")).toBe(attendance);
  await expect(readMenu("attendance.read")).resolves.toBe(attendance);
  expect(call).toHaveBeenCalledTimes(1);
});

it("isolates semester results and keeps saved changes available", async () => {
  const saved = { items: [{ grade: "A" }] };
  rememberMenuRead("grades.read", { semester: "2026-2" }, saved);
  expect(peekMenuRead("grades.read", { semester: "2027-1" })).toBeUndefined();
  await expect(readMenu("grades.read", { semester: "2026-2" })).resolves.toBe(saved);
  expect(call).not.toHaveBeenCalled();
  invalidateMenuReads("grades.read");
  expect(peekMenuRead("grades.read", { semester: "2026-2" })).toBeUndefined();
});

it("does not restore an invalidated result after an in-flight request completes", async () => {
  let complete!: (value: unknown) => void;
  call.mockReturnValueOnce(new Promise(resolve => { complete = resolve; }));
  const pending = readMenu("attendance.read");
  invalidateMenuReads();
  complete(["old"]);
  await pending;
  expect(peekMenuRead("attendance.read")).toBeUndefined();
  call.mockResolvedValueOnce(["new"]);
  await expect(readMenu("attendance.read")).resolves.toEqual(["new"]);
});

it("refreshes aging external reads without discarding their old value first", async () => {
  vi.useFakeTimers();
  try {
    call.mockResolvedValueOnce(["prior"]);
    await readMenu("focus.totals");
    vi.advanceTimersByTime(30000);
    expect(peekMenuRead("focus.totals")).toEqual(["prior"]);
    call.mockResolvedValueOnce(["latest"]);
    await expect(readMenu("focus.totals")).resolves.toEqual(["latest"]);
  } finally {
    vi.useRealTimers();
  }
});
