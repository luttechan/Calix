import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { test, expect, vi, afterEach } from "vitest";
const script = readFileSync(
  new URL("../scripts/canvas-modules.js", import.meta.url),
  "utf8",
);
function browser(routes, debug = false) {
  const fetch = vi.fn(async (input, options) => {
    const url = new URL(input);
    expect(url.origin).toBe("https://canvas.bufs.ac.kr");
    const route = routes[url.pathname] ?? [];
    if (typeof route === "function") return route(url, options);
    if (typeof route === "number")
      return new Response("{}", {
        status: route,
        headers: { "content-type": "application/json" },
      });
    return new Response(JSON.stringify(route), {
      headers: { "content-type": "application/json" },
    });
  });
  const window = {};
  const diagnostics = { debug, logs: [] };
  window[Symbol.for("calix.campus.reader")] = diagnostics;
  runInNewContext(script, {
    window,
    fetch,
    location: { origin: "https://canvas.bufs.ac.kr" },
    URL,
    AbortController,
    setTimeout,
    clearTimeout,
    Date,
  });
  return {
    reader: window[Symbol.for("calix.canvas.modules")],
    fetch,
    diagnostics,
  };
}
const base = "/api/v1/courses/2";
const file = (id = 3) => ({
  id,
  type: "File",
  content_id: 33,
  title: "영상",
  completion_requirement: { type: "must_view", completed: true },
});
afterEach(() => vi.useRealTimers());
test("native module HTTP diagnostics are opt-in and exclude query strings", async () => {
  const quiet = browser({});
  await quiet.reader.collect(2);
  expect(quiet.diagnostics.logs).toEqual([]);
  const traced = browser({}, true);
  await traced.reader.collect(2);
  expect(traced.diagnostics.logs).toContain(
    "HTTP START GET /api/v1/courses/2/modules",
  );
  expect(traced.diagnostics.logs).toContain(
    "HTTP RESPONSE 200 GET /api/v1/courses/2/modules",
  );
  expect(
    traced.diagnostics.logs.some(
      (value) => value.includes("?") || value.includes("include[]"),
    ),
  ).toBe(false);
});
test("native Canvas modules use inline items and reuse repeated file metadata", async () => {
  const { reader, fetch } = browser({
    [base + "/tabs"]: [],
    [base + "/modules"]: [
      {
        id: 1,
        name: "1주차",
        items_count: 2,
        items: [file(), { id: 4, type: "Assignment", content_id: 40 }],
      },
      { id: 2, items_count: 1, items: [file(8)] },
    ],
    [base + "/files/33"]: {
      "content-type": "video/mp4",
      url: "https://untrusted.invalid/video.mp4",
    },
  });
  const result = await reader.collect(2);
  expect(result.complete).toBe(true);
  expect(result.items).toHaveLength(2);
  expect(result.assignment_ids).toEqual([40]);
  expect(result.learningx.present).toBe(false);
  expect(
    fetch.mock.calls.filter(([u]) => u.pathname === base + "/files/33"),
  ).toHaveLength(1);
  expect(fetch.mock.calls.some(([u]) => u.pathname.endsWith("/items"))).toBe(
    false,
  );
});
test("omitted inline module items are fetched with pagination and page embeds are inspected without opening media", async () => {
  const { reader, fetch } = browser({
    [base + "/tabs"]: [],
    [base + "/modules"]: [{ id: 1, items_count: 2 }],
    [base + "/modules/1/items"]: (url) =>
      new Response(
        JSON.stringify(
          url.searchParams.has("page")
            ? [{ id: 5, type: "Page", page_url: "week-1", title: "1주차" }]
            : [
                {
                  id: 3,
                  type: "ExternalUrl",
                  external_url: "https://youtu.be/video",
                  title: "영상",
                },
              ],
        ),
        {
          headers: {
            "content-type": "application/json",
            ...(url.searchParams.has("page")
              ? {}
              : {
                  link: `<https://canvas.bufs.ac.kr${base}/modules/1/items?page=2>; rel="next"`,
                }),
          },
        },
      ),
    [base + "/pages/week-1"]: {
      page_id: 55,
      body: '<video src="https://external.invalid/video.mp4"></video>',
    },
  });
  const result = await reader.collect(2);
  expect(result.complete).toBe(true);
  expect(result.items).toHaveLength(2);
  expect(
    fetch.mock.calls.every(
      ([url]) => url.origin === "https://canvas.bufs.ac.kr",
    ),
  ).toBe(true);
});
test.each([200, 404, 403])(
  "empty, missing and forbidden modules stay distinct (%s)",
  async (status) => {
    const { reader } = browser({
      [base + "/tabs"]: [],
      [base + "/modules"]: status === 200 ? [] : status,
    });
    const result = await reader.collect(2);
    expect(result.items).toHaveLength(0);
    expect(result.learningx.present).toBe(false);
    expect(result.status).toBe(
      status === 200 ? "available" : status === 404 ? "missing" : "unavailable",
    );
    expect(result.complete).toBe(status !== 403);
  },
);
test("LearningX module entry survives a late tabs response", async () => {
  const { reader } = browser({
    [base + "/tabs"]: async () => {
      await new Promise((resolve) => setTimeout(resolve, 5));
      return new Response("[]", {
        headers: { "content-type": "application/json" },
      });
    },
    [base + "/modules"]: [
      {
        id: 1,
        items_count: 1,
        items: [
          {
            id: 3,
            type: "ExternalTool",
            title: "LearningX 주차학습",
            content_id: 9,
          },
        ],
      },
    ],
  });
  const result = await reader.collect(2);
  expect(result.learningx.present).toBe(true);
  expect(result.learningx.url).toBe(
    "https://canvas.bufs.ac.kr/courses/2/external_tools/9",
  );
});
test("one request times out after five seconds without authorizing an empty list", async () => {
  vi.useFakeTimers();
  const { reader } = browser({
    [base + "/modules"]: (_url, options) =>
      new Promise((_resolve, reject) =>
        options.signal.addEventListener("abort", () =>
          reject(Object.assign(new Error("aborted"), { name: "AbortError" })),
        ),
      ),
  });
  const pending = reader.collect(2);
  await vi.advanceTimersByTimeAsync(5001);
  const result = await pending;
  expect(result.complete).toBe(false);
  expect(result.warnings).toContain("모듈 응답 시간 초과");
  expect(vi.getTimerCount()).toBe(0);
});
test("overall module traversal stops at twelve seconds", async () => {
  vi.useFakeTimers();
  const items = Array.from({ length: 16 }, (_, i) => ({
    id: i + 1,
    type: "Page",
    page_url: "page-" + i,
    title: "영상",
  }));
  const routes = {
    [base + "/modules"]: [{ id: 1, items_count: items.length, items }],
  };
  for (let i = 0; i < 16; i++)
    routes[base + "/pages/page-" + i] = (_url, options) =>
      new Promise((resolve, reject) => {
        const timer = setTimeout(
          () =>
            resolve(
              new Response(
                JSON.stringify({ page_id: i + 1, body: "<video></video>" }),
                { headers: { "content-type": "application/json" } },
              ),
            ),
          4000,
        );
        options.signal.addEventListener("abort", () => {
          clearTimeout(timer);
          reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
        });
      });
  const { reader } = browser(routes),
    pending = reader.collect(2);
  await vi.advanceTimersByTimeAsync(12001);
  const result = await pending;
  expect(result.complete).toBe(false);
  expect(result.items.length).toBeLessThan(16);
  expect(result.warnings).toContain("모듈 응답 시간 초과");
  expect(vi.getTimerCount()).toBe(0);
});
test("authentication and user cancellation never become successful empty modules", async () => {
  const { reader } = browser({ [base + "/modules"]: 401 });
  await expect(reader.collect(2)).rejects.toThrow("AUTH_REQUIRED");
  const other = browser({
    [base + "/modules"]: (_url, options) =>
      new Promise((_resolve, reject) =>
        options.signal.addEventListener("abort", () =>
          reject(Object.assign(new Error("aborted"), { name: "AbortError" })),
        ),
      ),
  });
  const job = other.reader.collect(2);
  other.reader.cancel();
  await expect(job).rejects.toThrow("CANCELLED");
});
