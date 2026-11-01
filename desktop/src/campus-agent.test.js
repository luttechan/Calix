import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { expect, test, vi } from "vitest";

const script = readFileSync(
  new URL("../scripts/campus-agent.js", import.meta.url),
  "utf8",
);
function browser(prefix = "while(1);", invalid = null) {
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
    else
      value = {
        modules: [
          { content_data: { item_content_data: { content_type: "movie" } } },
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
  return { window, context, state, job, XHR };
}

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
