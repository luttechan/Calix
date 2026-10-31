(() => {
  if (location.origin !== "https://canvas.bufs.ac.kr") return;
  const key = Symbol.for("calix.campus.reader");
  if (window[key]) return;
  const state = { jobs: {}, courses: {} };
  window[key] = state;
  const identify = (url) => {
    try {
      const u = new URL(
        typeof url === "string" ? url : url.url || url.href,
        location.href,
      );
      if (u.origin !== location.origin) return null;
      return u.pathname.match(
        /^\/learningx\/api\/v1\/courses\/(\d+)\/(modules|lessons)(?:\/|$)/,
      );
    } catch {
      return null;
    }
  };
  const begin = (match) => {
    if (!match) return null;
    const row = (state.courses[match[1]] ||= {
      pending: 0,
      modules: false,
      lessons: false,
      failed: false,
      hasVideo: false,
    });
    row.pending++;
    return { row, done: false };
  };
  const finish = (token, match, ok, payload) => {
    if (!token || token.done) return;
    token.done = true;
    const row = token.row;
    row.pending--;
    if (!ok || !payload || typeof payload !== "object") {
      row.failed = true;
      return;
    }
    row[match[2]] = true;
    let remaining = 100000;
    const walk = (value, depth = 0) => {
      if (!value || typeof value !== "object" || depth > 16 || --remaining < 0)
        return;
      if (
        Object.entries(value).some(
          ([k, v]) =>
            /^(content_type|item_content_type|kind)$/.test(k) &&
            ["movie", "mp4", "zoom"].includes(v),
        )
      )
        row.hasVideo = true;
      for (const child of Object.values(value)) walk(child, depth + 1);
    };
    walk(payload);
    if (remaining < 0) row.failed = true;
  };
  const fetchOriginal = window.fetch.bind(window);
  window.fetch = function (...args) {
    const match = identify(args[0]),
      row = begin(match);
    return fetchOriginal(...args).then(
      (response) => {
        if (row)
          response
            .clone()
            .json()
            .then(
              (data) => finish(row, match, response.ok, data),
              () => finish(row, match, false),
            );
        return response;
      },
      (error) => {
        finish(row, match, false);
        throw error;
      },
    );
  };
  const xhrOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (...args) {
    const result = xhrOpen.apply(this, args);
    const match = identify(args[1]);
    this.addEventListener(
      "loadend",
      () => {
        try {
          finish(
            this.__calixReadRow,
            match,
            this.status >= 200 && this.status < 300,
            this.responseType === "json"
              ? this.response
              : JSON.parse(this.responseText),
          );
        } catch {
          finish(this.__calixReadRow, match, false);
        }
      },
      { once: true },
    );
    this.__calixReadMatch = match;
    return result;
  };
  const xhrSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (...args) {
    this.__calixReadRow = begin(this.__calixReadMatch);
    try {
      return xhrSend.apply(this, args);
    } catch (error) {
      finish(this.__calixReadRow, this.__calixReadMatch, false);
      throw error;
    }
  };
  const jsonRequest = async (url) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetchOriginal(url, {
        credentials: "include",
        redirect: "error",
        signal: controller.signal,
      });
      if (response.status === 401 || response.status === 403)
        throw Error("AUTH_REQUIRED");
      if (
        !response.ok ||
        !/json/i.test(response.headers.get("content-type") || "")
      )
        throw Error("HTTP_" + response.status);
      const text = await response.text();
      if (text.length > 16000000) throw Error("RESPONSE_TOO_LARGE");
      return { response, value: JSON.parse(text) };
    } finally {
      clearTimeout(timer);
    }
  };
  const list = async (path, params = {}) => {
    let url = new URL(path, location.origin);
    for (const [key, value] of Object.entries(params))
      for (const v of Array.isArray(value) ? value : [value])
        url.searchParams.append(key, v);
    const expected = url.pathname,
      visited = new Set(),
      rows = [];
    for (let page = 0; page < 1000; page++) {
      if (
        url.origin !== location.origin ||
        url.pathname !== expected ||
        visited.has(url.href)
      )
        throw Error("UNSAFE_PAGE");
      visited.add(url.href);
      const { response, value } = await jsonRequest(url);
      if (!Array.isArray(value)) throw Error("INVALID_LIST");
      rows.push(...value);
      if (rows.length > 100000) throw Error("TOO_MANY_ITEMS");
      const next = (response.headers.get("link") || "")
        .split(",")
        .map((s) => s.trim())
        .find((s) => /;\s*rel=["']?next["']?(?:;|$)/i.test(s));
      if (!next) return rows;
      const match = next.match(/^<([^>]+)>/);
      if (!match) throw Error("INVALID_PAGE");
      url = new URL(match[1], url);
    }
    throw Error("TOO_MANY_PAGES");
  };
  const pick = (value, keys) =>
    Object.fromEntries(
      keys.filter((k) => Object.hasOwn(value, k)).map((k) => [k, value[k]]),
    );
  const submission = (s) =>
    s && typeof s === "object"
      ? pick(s, [
          "assignment_id",
          "workflow_state",
          "submitted_at",
          "cached_due_date",
        ])
      : s;
  const assignment = (a) => {
    if (!a || typeof a !== "object") return a;
    const row = pick(a, [
      "id",
      "name",
      "due_at",
      "html_url",
      "published",
      "is_quiz_assignment",
      "submission_types",
    ]);
    if (a.submission) row.submission = submission(a.submission);
    return row;
  };
  state.start = (id, operation, course) => {
    state.jobs = { [id]: { status: "pending" } };
    (async () => {
      if (operation === "identity") {
        const { value: profile } = await jsonRequest(
          "/api/v1/users/self/profile",
        );
        if (typeof profile.id === "number" && !Number.isSafeInteger(profile.id))
          throw Error("INVALID_OWNER");
        const owner = String(profile.id);
        if (!/^[1-9]\d{0,18}$/.test(owner)) throw Error("INVALID_OWNER");
        const courses = await list("/api/v1/courses", {
          enrollment_type: "student",
          enrollment_state: "active",
          per_page: 100,
        });
        const unique = new Map();
        for (const c of courses) {
          const id = Number(c?.id);
          if (!Number.isSafeInteger(id) || id <= 0)
            throw Error("INVALID_COURSE");
          unique.set(id, {
            id,
            name: String(c.name || c.longName || c.course_code || `과목 ${id}`),
          });
        }
        if (!unique.size) throw Error("NO_COURSES");
        return { owner, courses: [...unique.values()] };
      }
      if (
        operation === "assignments" &&
        Number.isSafeInteger(course) &&
        course > 0
      ) {
        const base = `/api/v1/courses/${course}`,
          responses = {};
        let rows = null;
        try {
          rows = await list(base + "/assignments", {
            "exclude_response_fields[]": ["description", "rubric"],
            "include[]": ["submission"],
            override_assignment_dates: "true",
            per_page: 100,
          });
          responses[base + "/assignments"] = { data: rows.map(assignment) };
        } catch (error) {
          responses[base + "/assignments"] = { error: String(error.message) };
        }
        if (!rows?.length) {
          const groups = await list(base + "/assignment_groups", {
            "exclude_response_fields[]": ["description", "rubric"],
            "include[]": ["assignments", "discussion_topic"],
            override_assignment_dates: "true",
            per_page: 100,
          });
          responses[base + "/assignment_groups"] = {
            data: groups.map((g) => ({
              name: g.name || "",
              assignments: Array.isArray(g.assignments)
                ? g.assignments.map(assignment)
                : g.assignments,
            })),
          };
          rows = groups.flatMap((g) =>
            Array.isArray(g.assignments) ? g.assignments : [],
          );
        }
        const states = [
          "submitted",
          "graded",
          "pending_review",
          "unsubmitted",
          "untaken",
        ];
        if (
          rows.some(
            (a) =>
              a?.published !== false &&
              a?.is_quiz_assignment !== true &&
              !(a?.submission_types || []).includes("online_quiz") &&
              !states.includes(a?.submission?.workflow_state),
          )
        ) {
          responses[base + "/students/submissions"] = {
            data: (
              await list(base + "/students/submissions", { per_page: 100 })
            ).map(submission),
          };
        }
        return responses;
      }
      throw Error("UNSUPPORTED_OPERATION");
    })().then(
      (value) => {
        if (state.jobs[id]) state.jobs[id] = { status: "ready", value };
      },
      (error) => {
        if (state.jobs[id])
          state.jobs[id] = {
            status: "error",
            error: String(error.message || "BROWSER_ERROR").slice(0, 200),
          };
      },
    );
    return true;
  };
})();
