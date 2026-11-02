import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import { runInNewContext } from "node:vm";
import { expect, test, vi } from "vitest";

const script = readFileSync(
  new URL("../scripts/campus-agent.js", import.meta.url),
  "utf8",
).replace(
  "__CALIX_MEDIA_RULES__",
  readFileSync(
    new URL("../../learning_calendar/media_types.json", import.meta.url),
    "utf8",
  ),
);
function browser(
  prefix = "while(1);",
  invalid = null,
  media = { content_type: "movie" },
) {
  class XHR {
    callbacks = [];
    open() {}
    addEventListener(_event, callback) {
      this.callbacks.push(callback);
    }
    send() {
      this.status = 200;
      this.responseType = "";
      this.responseText =
        prefix + JSON.stringify({ lessons: [{ content_type: "movie" }] });
      for (const callback of this.callbacks) callback();
    }
  }
  const fetch = vi.fn(async (input) => {
    const url = new URL(input, "https://canvas.bufs.ac.kr");
    const headers = { "content-type": "application/json" };
    let value;
    if (url.pathname.endsWith("/profile")) value = { id: 7 };
    else if (url.pathname === "/api/v1/courses") {
      value = [
        {
          id: url.searchParams.get("page") === "2" ? 2 : 1,
          name: "while(1); 수업",
        },
      ];
      if (!url.searchParams.has("page"))
        headers.link =
          '<https://canvas.bufs.ac.kr/api/v1/courses?page=2>; rel="next"';
    } else if (url.pathname.endsWith("/assignments"))
      value = [{ id: 3, name: "과제", submission_types: ["online_upload"] }];
    else if (url.pathname.endsWith("/students/submissions"))
      value = [{ assignment_id: 3, workflow_state: "submitted" }];
    else if (url.pathname.endsWith("/lessons"))
      value = { lessons: [{ id: 1 }] };
    else
      value = {
        modules: [
          {
            module_items: [
              {
                module_item_id: 11,
                completed: false,
                attendance_status: "none",
                content_type: "attendance_item",
                content_data: {
                  item_content_type: "commons",
                  item_content_data: media,
                },
              },
            ],
          },
        ],
      };
    return new Response(
      invalid === null ? prefix + JSON.stringify(value) : invalid,
      { headers },
    );
  });
  const window = { fetch };
  const context = {
    window,
    location: {
      origin: "https://canvas.bufs.ac.kr",
      href: "https://canvas.bufs.ac.kr/courses/1",
    },
    URL,
    Headers,
    TextEncoder,
    crypto: webcrypto,
    Uint8Array,
    XMLHttpRequest: XHR,
    AbortController,
    setTimeout,
    clearTimeout,
  };
  runInNewContext(script, context);
  const state = window[Symbol.for("calix.campus.reader")];
  const job = async (operation, course = null) => {
    const id = "test";
    state.start(id, operation, course);
    await vi.waitFor(() => expect(state.jobs[id].status).not.toBe("pending"));
    return state.jobs[id];
  };
  return { window, context, state, job, XHR, fetch };
}

test("attendance requests join all four read-only endpoints and strip private metadata", async () => {
  const { fetch, job } = browser();
  fetch.mockImplementation(async (input) => {
    const path = new URL(input, "https://canvas.bufs.ac.kr").pathname;
    const value = path.endsWith("/lessons")
      ? [
          {
            week_position: 1,
            lessons: [
              {
                lesson_position: 1,
                class_date: "2026-11-03",
                student_name: "PRIVATE",
              },
            ],
          },
        ]
      : path.endsWith("/lessons/attendances")
        ? [
            {
              week_position: 1,
              lesson_position: 1,
              attendance_status: "attendance",
              student_name: "PRIVATE",
            },
          ]
        : path.endsWith("/summary")
          ? {
              attendance_summaries: {
                11: {
                  item_id: 11,
                  attendance_status: "late",
                  student_name: "PRIVATE",
                },
              },
            }
          : {
              attendance_items: [
                {
                  item_id: 11,
                  title: "Video",
                  use_attendance: true,
                  item_content_data: {
                    content_type: "movie",
                    view_url: "PRIVATE",
                  },
                },
              ],
            };
    return new Response("while(1);" + JSON.stringify(value), {
      headers: { "content-type": "application/json" },
    });
  });
  const result = await job("attendance", 1);
  expect(result.status).toBe("ready");
  expect(Object.keys(result.value)).toHaveLength(4);
  expect(JSON.stringify(result.value)).not.toContain("PRIVATE");
  expect(
    fetch.mock.calls.every(([, options]) => options.credentials === "include"),
  ).toBe(true);
});

test("one attendance endpoint failure preserves the successful responses", async () => {
  const { fetch, job } = browser();
  fetch.mockImplementation(async (input) => {
    const path = new URL(input, "https://canvas.bufs.ac.kr").pathname;
    return path.endsWith("/summary")
      ? new Response("", { status: 404 })
      : new Response(
          JSON.stringify(
            path.endsWith("attendance_items") ? { attendance_items: [] } : [],
          ),
          { headers: { "content-type": "application/json" } },
        );
  });
  const result = await job("attendance", 1);
  expect(result.status).toBe("ready");
  expect(
    result.value["/learningx/api/v1/courses/1/attendance_items/summary"].error,
  ).toBe("HTTP_404");
  expect(result.value["/learningx/api/v1/courses/1/lessons"].data).toEqual([]);
});

test("submitted assignments still fetch feedback and preserve late and graded facts", async () => {
  const { fetch, job } = browser();
  fetch.mockImplementation(async (input) => {
    const url = new URL(input, "https://canvas.bufs.ac.kr");
    const value = url.pathname.endsWith("/assignments")
      ? [
          {
            id: 3,
            name: "Task",
            submission_types: ["online_upload"],
            submission: { workflow_state: "graded" },
          },
        ]
      : [
          {
            assignment_id: 3,
            workflow_state: "graded",
            late: true,
            grade: "A",
            submission_comments: [
              {
                author_name: "Instructor",
                comment: "Well written",
                created_at: "2026-11-03T00:00:00Z",
                author_email: "PRIVATE",
              },
            ],
          },
        ];
    return new Response(JSON.stringify(value), {
      headers: { "content-type": "application/json" },
    });
  });
  const result = await job("assignments", 1);
  const s = result.value["/api/v1/courses/1/students/submissions"].data[0];
  expect(s.late).toBe(true);
  expect(s.grade).toBe("A");
  expect(s.submission_comments[0].comment).toBe("Well written");
  expect(JSON.stringify(s)).not.toContain("PRIVATE");
  const call = fetch.mock.calls.find(([input]) =>
    String(input).includes("students/submissions"),
  );
  expect(new URL(call[0]).searchParams.getAll("include[]")).toContain(
    "submission_comments",
  );
  expect(new URL(call[0]).searchParams.has("student_ids[]")).toBe(false);
});

test.each(["", "while(1);", "\uFEFF \nwhile ( 1 ) ;\n"])(
  "일반 응답과 Canvas 보호 접두사에서 계정 및 모든 과목을 읽는다 (%s)",
  async (prefix) => {
    const { job } = browser(prefix);
    const result = await job("identity");
    expect(result.status).toBe("ready");
    expect(result.value.owner).toBe("7");
    expect(result.value.courses).toHaveLength(2);
    expect(result.value.courses[0].name).toBe("while(1); 수업");
  },
);
test("접두사가 있는 과제와 제출 상태를 읽는다", async () => {
  const { job } = browser();
  const result = await job("assignments", 1);
  expect(result.status).toBe("ready");
  expect(result.value["/api/v1/courses/1/assignments"].data[0].name).toBe(
    "과제",
  );
  expect(JSON.stringify(result.value)).toContain("submitted");
});
test("영상 Fetch와 XHR의 보호 접두사도 동일하게 처리한다", async () => {
  const { window, state, XHR } = browser();
  await window.fetch("/learningx/api/v1/courses/1/modules");
  const xhr = new XHR();
  xhr.open("GET", "/learningx/api/v1/courses/1/lessons");
  xhr.send();
  await vi.waitFor(() => expect(state.courses[1].pending).toBe(0));
  expect(state.courses[1].modules).toBe(true);
  expect(state.courses[1].lessons).toBe(true);
  expect(state.courses[1].hasVideo).toBe(true);
  expect(state.courses[1].failed).toBe(false);
});
test.each([
  "<html>로그인</html>",
  'while(1);globalThis.executed=true;{"id":7}',
  'while(1);while(1);{"id":7}',
])(
  "허용되지 않은 본문을 실행하거나 빈 목록으로 취급하지 않는다 (%s)",
  async (invalid) => {
    const { job, context } = browser("", invalid);
    expect((await job("identity")).error).toBe("INVALID_JSON");
    expect(context.executed).toBeUndefined();
  },
);

const compatibleTypes = [
  "movie",
  "ssz",
  "syncthink",
  "estage",
  "xenoglobal",
  "oncast",
  "screenlecture",
  "lecturecam",
  "readystream",
  "webstudio",
  "everlec",
  "movie360",
  "mp4",
  "zoom",
  "audio",
  "youtube",
  "remix",
  "metaverse_conference",
  "video_conference",
  "external_youtube",
  "external_video",
];
test.each(compatibleTypes)(
  "학교 플레이어 영상 유형 %s를 인식한다",
  async (content_type) => {
    const { window, state } = browser("while(1);", null, { content_type });
    await window.fetch("/learningx/api/v1/courses/1/modules");
    await vi.waitFor(() => expect(state.courses[1].pending).toBe(0));
    expect(state.courses[1]).toMatchObject({
      hasVideo: true,
      videoCount: 1,
      unsupported: false,
    });
    expect(state.courses[1].mediaByItem[11]).toMatchObject({
      video: true,
      kind: content_type,
    });
  },
);
test("새로운 재생형 자료는 진도 지원과 재생 시간으로 인식한다", async () => {
  const { window, state } = browser("", null, {
    content_type: "future_player",
    progress_support: true,
    duration: 123.5,
  });
  await window.fetch("/learningx/api/v1/courses/1/modules");
  await vi.waitFor(() => expect(state.courses[1].pending).toBe(0));
  expect(state.courses[1]).toMatchObject({
    hasVideo: true,
    videoCount: 1,
    unsupported: false,
  });
  expect(state.courses[1].mediaByItem[11]).toMatchObject({
    video: true,
    kind: "movie",
    source_type: "future_player",
  });
});
test("판별 불가능한 자료를 영상 없는 과목으로 확정하지 않는다", async () => {
  const { window, state } = browser("", null, {
    content_type: "unknown_learning_content",
  });
  await window.fetch("/learningx/api/v1/courses/1/modules");
  await vi.waitFor(() => expect(state.courses[1].pending).toBe(0));
  expect(state.courses[1].unsupported).toBe(true);
});
test("일반 파일은 영상이나 미지원 영상으로 오인하지 않는다", async () => {
  const { window, state } = browser("", null, { content_type: "pdf" });
  await window.fetch("/learningx/api/v1/courses/1/modules");
  await vi.waitFor(() => expect(state.courses[1].pending).toBe(0));
  expect(state.courses[1]).toMatchObject({
    hasVideo: false,
    videoCount: 0,
    unsupported: false,
  });
});
test("중단 시 진행 중인 API 요청을 취소하고 늦은 완료를 폐기한다", async () => {
  const { state, fetch } = browser();
  fetch.mockImplementation(
    (_url, options) =>
      new Promise((_resolve, reject) =>
        options.signal.addEventListener(
          "abort",
          () => reject(Error("ABORTED")),
          { once: true },
        ),
      ),
  );
  state.start("cancelled", "identity", null);
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
  const signal = fetch.mock.calls[0][1].signal;
  state.cancel();
  expect(signal.aborted).toBe(true);
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(Object.keys(state.jobs)).toHaveLength(0);
});

async function seededManifest() {
  const value = browser();
  await value.window.fetch(
    "/learningx/api/v1/courses/1/modules?include_detail=true",
    { headers: { Authorization: "Bearer fixture-token" } },
  );
  await value.window.fetch("/learningx/api/v1/courses/1/lessons", {
    headers: { Authorization: "Bearer fixture-token" },
  });
  await vi.waitFor(() => expect(value.state.courses["1"].pending).toBe(0));
  return value;
}
test("unchanged content is detected without opening the course again", async () => {
  const { state, fetch } = await seededManifest();
  const baseline = await state.videoManifest(1, false);
  const before = fetch.mock.calls.length;
  const fresh = await state.videoManifest(1, true);
  expect(baseline.cacheable).toBe(true);
  expect(baseline.complete).toBe(true);
  expect(fresh.digest).toBe(baseline.digest);
  expect(fresh.states["11"]).toBe(false);
  expect(fetch.mock.calls.length - before).toBe(2);
  expect(JSON.stringify(fresh)).not.toContain("fixture-token");
  expect(fetch.mock.calls.at(-1)[1].cache).toBe("no-cache");
});
test.each(["completion", "new-video", "deadline"])(
  "a changed %s invalidates the saved fingerprint",
  async (change) => {
    const { state, fetch } = await seededManifest();
    const before = await state.videoManifest(1, false);
    const original = fetch.getMockImplementation();
    fetch.mockImplementation(async (input, options) => {
      const response = await original(input, options);
      if (
        !new URL(input, "https://canvas.bufs.ac.kr").pathname.endsWith(
          "/modules",
        )
      )
        return response;
      const value = JSON.parse(
        (await response.text()).replace("while(1);", ""),
      );
      const item = value.modules[0].module_items[0];
      if (change === "completion") item.completed = true;
      if (change === "deadline") item.due_at = "2026-12-01T12:00:00Z";
      if (change === "new-video")
        value.modules[0].module_items.push({ ...item, module_item_id: 12 });
      return new Response(JSON.stringify(value), {
        headers: { "content-type": "application/json" },
      });
    });
    const after = await state.videoManifest(1, true);
    expect(after.cacheable).toBe(true);
    expect(after.digest).not.toBe(before.digest);
  },
);
test("unknown completion and failed probes never authorize cached content", async () => {
  const { state, fetch } = await seededManifest();
  const original = fetch.getMockImplementation();
  fetch.mockImplementation(async (input, options) => {
    const response = await original(input, options);
    if (
      !new URL(input, "https://canvas.bufs.ac.kr").pathname.endsWith("/modules")
    )
      return response;
    const value = JSON.parse((await response.text()).replace("while(1);", ""));
    delete value.modules[0].module_items[0].completed;
    return new Response(JSON.stringify(value), {
      headers: { "content-type": "application/json" },
    });
  });
  expect((await state.videoManifest(1, true)).complete).toBe(false);
  fetch.mockRejectedValue(new Error("NETWORK_FAILED"));
  expect((await state.videoManifest(1, true)).cacheable).toBe(false);
});
test("without LearningX authentication a probe safely falls back without requests", async () => {
  const { state, fetch } = browser();
  expect((await state.videoManifest(1, true)).cacheable).toBe(false);
  expect(fetch).not.toHaveBeenCalled();
});
