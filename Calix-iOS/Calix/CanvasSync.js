if (location.origin !== "https://canvas.bufs.ac.kr") throw Error("AUTH_REQUIRED");

const parse = (body) => JSON.parse(body.trimStart().replace(/^while\s*\(\s*1\s*\)\s*;/, ""));
const request = async (path, learning = false) => {
    const url = new URL(path, location.origin);
    if (url.origin !== location.origin) throw Error("UNEXPECTED_ORIGIN");
    const headers = { Accept: "application/json" };
    if (learning) {
        const token = document.cookie.match(/(?:^|;\s*)xn_api_token=([^;]*)/)?.[1];
        if (token) headers.Authorization = "Bearer " + decodeURIComponent(token);
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
        const res = await fetch(url, { credentials: "same-origin", redirect: "error", headers, signal: controller.signal });
        if (res.status === 401 || res.status === 403) throw Error("AUTH_REQUIRED");
        if (!res.ok) throw Error(`HTTP_${res.status}`);
        const body = await res.text();
        if (body.length > 8000000) throw Error("RESPONSE_TOO_LARGE");
        return { data: parse(body), next: res.headers.get("Link")?.match(/<([^>]+)>;\s*rel="next"/)?.[1] };
    } finally { clearTimeout(timer); }
};

const list = async (initial) => {
    const rows = [];
    let next = initial;
    for (let page = 0; next && page < 25; page++) {
        const value = await request(next);
        if (!Array.isArray(value.data)) throw Error("INVALID_LIST");
        rows.push(...value.data);
        next = value.next;
    }
    if (next) throw Error("TOO_MANY_PAGES");
    return rows;
};

const id = (value) => {
    const text = String(value ?? "");
    return /^[1-9]\d{0,18}$/.test(text) && (typeof value !== "number" || Number.isSafeInteger(value)) ? text : null;
};
const clip = (value, size = 500) => typeof value === "string" ? value.slice(0, size) : "";
const date = (value) => typeof value === "string" && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : null;
const link = (value) => {
    try {
        if (!value) return null;
        const address = new URL(value, location.origin);
        return address.origin === location.origin ? address.href : null;
    } catch { return null; }
};
const mediaTypes = new Set(["movie", "ssz", "syncthink", "estage", "xenoglobal", "oncast", "screenlecture", "lecturecam", "readystream", "webstudio", "everlec", "movie360", "mp4", "zoom", "audio", "youtube", "remix", "metaverse_conference", "video_conference", "external_youtube", "external_video"]);

const readVideos = (course, courseID, body) => {
    const roots = Array.isArray(body) ? body : body?.modules;
    if (!Array.isArray(roots)) throw Error("INVALID_MODULES");
    const events = new Map();
    const inspect = (row, depth) => {
        if (!row || typeof row !== "object" || depth > 10 || row.published === false) return;
        const data = row.content_data;
        const media = data?.item_content_data;
        const type = media?.content_type || data?.item_content_type || row.content_type;
        const itemID = id(row.module_item_id);
        const movingImage = mediaTypes.has(type) || (type === "embed" && mediaTypes.has(media?.content_subtype)) ||
            (media?.progress_support === true && Number(media.duration) > 0);
        const title = clip(row.title || data?.title || media?.title);
        if (itemID && data && movingImage && title) {
            const key = `canvas:${courseID}:video:${itemID}`;
            events.set(key, { id: key, title, course, kind: "영상", due: date(row.due_at || data.due_at),
                done: row.completed === true, url: link(row.html_url) || link(`/courses/${courseID}/modules`) });
        }
        for (const child of Object.values(row)) inspect(child, depth + 1);
    };
    inspect(roots, 0);
    return [...events.values()];
};

const readAttendance = async (course, courseID, root) => {
    const [weeks, statuses, items, summaries] = await Promise.all([
        request(root + "/lessons", true), request(root + "/lessons/attendances", true),
        request(root + "/attendance_items?include_detail=true", true), request(root + "/attendance_items/summary?only_use_attendance=true", true)
    ]);
    if (!Array.isArray(weeks.data) || !Array.isArray(statuses.data) || !Array.isArray(items.data?.attendance_items) ||
        !summaries.data?.attendance_summaries) throw Error("INVALID_ATTENDANCE");
    const index = new Map(statuses.data.map((row) => [`${row.week_position}:${row.lesson_position}`, clip(row.attendance_status, 80)]));
    const rows = new Map();
    for (const week of weeks.data) {
        for (const lesson of (Array.isArray(week.lessons) ? week.lessons : [])) {
            const w = week.week_position, l = lesson.lesson_position;
            if (!Number.isSafeInteger(w) || !Number.isSafeInteger(l)) continue;
            const key = `lesson:${courseID}:${w}:${l}`;
            rows.set(key, { id: key, course, title: `${w}주차 ${l}차시`, status: index.get(`${w}:${l}`) || "none",
                date: date(lesson.makeup_date || lesson.class_date || lesson.display_class_date) });
        }
    }
    for (const item of items.data.attendance_items) {
        const itemID = id(item.item_id);
        if (!itemID || item.published === false || item.use_attendance === false) continue;
        const key = `item:${courseID}:${itemID}`;
        const summary = summaries.data.attendance_summaries[itemID];
        rows.set(key, { id: key, course, title: clip(item.title) || "학습 출결", status: clip(summary?.attendance_status, 80) || "none", date: date(item.due_at) });
    }
    return [...rows.values()];
};

const profile = (await request("/api/v1/users/self/profile")).data;
const owner = id(profile?.id);
if (!owner) throw Error("AUTH_REQUIRED");
if (expectedOwner && owner !== expectedOwner) throw Error("ACCOUNT_CHANGED");
const courses = await list("/api/v1/courses?enrollment_type=student&enrollment_state=active&per_page=100");
if (courses.length > 180) throw Error("COURSE_LIMIT");

const readAssignments = async (base) => {
    const query = "exclude_response_fields[]=description&override_assignment_dates=true&per_page=100";
    try {
        const result = await list(base + "/assignments?include[]=submission&" + query);
        if (result.length) return result;
        try {
            const groups = await list(base + "/assignment_groups?include[]=assignments&" + query);
            return groups.flatMap((group) => Array.isArray(group.assignments) ? group.assignments : []);
        } catch { return result; }
    } catch {
        const groups = await list(base + "/assignment_groups?include[]=assignments&" + query);
        return groups.flatMap((group) => Array.isArray(group.assignments) ? group.assignments : []);
    }
};

const gather = async (row) => {
    const courseID = id(row?.id);
    if (!courseID) throw Error("INVALID_COURSE");
    const name = clip(row.name || row.course_code) || `과목 ${courseID}`;
    const base = `/api/v1/courses/${courseID}`;
    const learning = `/learningx/api/v1/courses/${courseID}`;
    const [assigned, videos, attendance, submissions] = await Promise.allSettled([
        readAssignments(base),
        request(learning + "/modules?include_detail=true", true).then((response) => readVideos(name, courseID, response.data)),
        includeAttendance ? readAttendance(name, courseID, learning) : Promise.resolve(null),
        list(base + `/students/submissions?student_ids[]=${owner}&include[]=submission_comments&include[]=rubric_assessment&per_page=100`)
    ]);
    const enriched = submissions.status === "fulfilled" ? new Map(submissions.value.filter((row) => id(row.user_id) === owner)
        .map((row) => [id(row.assignment_id), row])) : new Map();
    const assignments = assigned.status === "fulfilled" ? assigned.value.flatMap((item) => {
        const assignmentID = id(item?.id);
        if (!assignmentID || !item.name || item.published === false) return [];
        const submission = enriched.get(assignmentID) || item.submission;
        const workflow = clip(submission?.workflow_state, 40);
        const labels = [];
        if (submission?.missing) labels.push("미제출");
        if (submission?.late) labels.push("지각 제출");
        if (workflow === "graded") labels.push("채점 완료");
        else if (workflow === "submitted" || submission?.submitted_at) labels.push("제출 완료");
        for (const comment of (Array.isArray(submission?.submission_comments) ? submission.submission_comments : [])) {
            if (comment?.comment) labels.push(clip(comment.comment, 2000));
        }
        for (const criterion of Object.values(submission?.rubric_assessment || {})) {
            if (criterion?.comments) labels.push(clip(criterion.comments, 2000));
        }
        return [{ id: `canvas:${courseID}:assignment:${assignmentID}`, title: clip(item.name), course: name, kind: "과제",
            due: date(item.due_at), done: Boolean(submission?.submitted_at) || workflow === "submitted" || workflow === "graded",
            url: link(item.html_url) || link(`${base.replace("/api/v1", "")}/assignments/${assignmentID}`), feedback: labels.join("\n").slice(0, 6000) || null }];
    }) : null;
    return { id: courseID, name, assignments, videos: videos.status === "fulfilled" ? videos.value : null,
        attendance: attendance.status === "fulfilled" ? attendance.value : null };
};

const output = [];
for (let i = 0; i < courses.length; i += 3) output.push(...await Promise.all(courses.slice(i, i + 3).map(gather)));
return JSON.stringify({ owner, courses: output });
