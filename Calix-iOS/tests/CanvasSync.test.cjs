const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { test } = require("node:test");

const origin = "https://canvas.bufs.ac.kr";
const script = fs.readFileSync(path.join(__dirname, "../Calix/CanvasSync.js"), "utf8");
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const sync = new AsyncFunction("expectedOwner", "includeAttendance", "location", "document", "fetch", script);
const root = "/learningx/api/v1/courses/42";
const fixtures = new Map([
    ["/api/v1/users/self/profile", { id: 13 }],
    ["/api/v1/courses", [{ id: 42, name: "Algorithms" }]],
    ["/api/v1/courses/42/assignments", [{
        id: 4, name: "Project", due_at: "2026-11-20T23:59:00+09:00", html_url: "https://outside.invalid/",
        submission: { workflow_state: "graded", submission_comments: [{ comment: "Good" }] },
    }]],
    ["/api/v1/courses/42/students/submissions", [{
        assignment_id: 4, user_id: 13, workflow_state: "graded", submission_comments: [{ comment: "Good" }],
        rubric_assessment: { clarity: { comments: "Clear reasoning" } },
    }]],
    [root + "/modules", { modules: [{ items: [{
        title: "Lecture", module_item_id: 8, completed: true, content_data: { item_content_type: "readystream" },
    }] }] }],
    [root + "/lessons", [{ week_position: 2, lessons: [{ lesson_position: 1, class_date: "2026-11-20" }] }]],
    [root + "/lessons/attendances", [{ week_position: 2, lesson_position: 1, attendance_status: "excused" }]],
    [root + "/attendance_items", { attendance_items: [{ item_id: 8, title: "Lecture" }] }],
    [root + "/attendance_items/summary", { attendance_summaries: { 8: { attendance_status: "attendance" } } }],
]);

function transport({ fail, carryNext = false } = {}) {
    return async (url, settings) => {
        assert.equal(url.origin, origin);
        assert.equal(settings.credentials, "same-origin");
        assert.equal(settings.redirect, "error");
        if (url.pathname.startsWith(root)) assert.equal(settings.headers.Authorization, "Bearer fixture-token");
        if (fail === url.pathname) throw Error("offline");
        assert.ok(fixtures.has(url.pathname), `unexpected path ${url.pathname}`);
        const page = url.searchParams.get("page");
        const payload = page === "2" ? [] : fixtures.get(url.pathname);
        const headers = new Headers();
        if (carryNext && url.pathname === "/api/v1/courses" && !page) {
            headers.set("Link", `<${origin}/api/v1/courses?page=2>; rel="next"`);
        }
        return { ok: true, headers, text: async () => "while(1);" + JSON.stringify(payload) };
    };
}

const run = (owner, attendance, fetch) => sync(owner, attendance, { origin }, { cookie: "xn_api_token=fixture-token" }, fetch).then(JSON.parse);

test("projects paginated assignments, LearningX video, and explicit attendance states", async () => {
    const value = await run("13", true, transport({ carryNext: true }));
    assert.equal(value.owner, "13");
    const [course] = value.courses;
    assert.equal(course.assignments[0].done, true);
    assert.match(course.assignments[0].feedback, /Good/);
    assert.match(course.assignments[0].feedback, /Clear reasoning/);
    assert.equal(course.assignments[0].url, origin + "/courses/42/assignments/4");
    assert.equal(course.assignments[0].due, "2026-11-20T14:59:00.000Z");
    assert.equal(course.videos[0].done, true);
    assert.deepEqual(course.attendance.map((row) => row.status), ["excused", "attendance"]);
    assert.doesNotMatch(JSON.stringify(value), /fixture-token/);
});

test("marks partial lists unavailable while preserving successfully fetched data", async () => {
    const [course] = (await run("", false, transport({ fail: root + "/modules" }))).courses;
    assert.equal(course.videos, null);
    assert.equal(course.attendance, null);
    assert.equal(course.assignments.length, 1);
});

test("rejects switching accounts or executing outside the school origin", async () => {
    await assert.rejects(run("99", true, transport()), /ACCOUNT_CHANGED/);
    await assert.rejects(sync("", false, { origin: "https://outside.invalid" }, {}, transport()), /AUTH_REQUIRED/);
});
