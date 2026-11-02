(() => {
  if (location.origin !== "https://canvas.bufs.ac.kr") return;
  const key = Symbol.for("calix.campus.reader");
  if (window[key]) return;
  const mediaRules = __CALIX_MEDIA_RULES__;
  const videoTypes = new Set(mediaRules.video);
  const nonVideoTypes = new Set(mediaRules.non_video);
  const videoSubtypes = new Set(mediaRules.video_subtypes);
  const controllers = new Set();
  let learningAuthorization = "";
  const captured = new Map();
  const rememberAuthorization = (value) => {
    if (
      typeof value === "string" &&
      /^Bearer /i.test(value) &&
      value.length < 16384
    )
      learningAuthorization = value;
  };
  const state = { jobs: {}, courses: {}, debug: false, logs: [] };
  const parseCampusJSON = (text) => {
    if (typeof text !== "string" || text.length > 16000000)
      throw Error("RESPONSE_TOO_LARGE");
    const json = text.trimStart().replace(/^while\s*\(\s*1\s*\)\s*;/, "");
    try {
      return JSON.parse(json);
    } catch {
      throw Error("INVALID_JSON");
    }
  };
  const log = (message) => {
    if (state.debug) {
      state.logs.push(message);
      if (state.logs.length > 100) state.logs.shift();
    }
  };
  state.cancel = () => {
    for (const controller of controllers) controller.abort();
    controllers.clear();
    state.jobs = {};
  };
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
      videoCount: 0,
      unsupported: false,
      mediaByItem: Object.create(null),
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
    const list = Array.isArray(payload) ? payload : payload[match[2]];
    if (!Array.isArray(list)) {
      row.failed = true;
      return;
    }
    row[match[2]] = true;
    if (JSON.stringify(payload).length <= 2000000) {
      if (captured.size >= 2 && !captured.has(match[1])) captured.clear();
      const entry = captured.get(match[1]) || {};
      entry[match[2]] = payload;
      captured.set(match[1], entry);
    } else captured.delete(match[1]);
    let remaining = 100000,
      videoCount = 0;
    const walk = (value, depth = 0) => {
      if (!value || typeof value !== "object" || depth > 16 || --remaining < 0)
        return;
      if (value.published === false) return;
      if (
        value.content_type === "attendance_item" &&
        (!value.content_data || typeof value.content_data !== "object")
      )
        row.unsupported = true;
      if (value.content_data && typeof value.content_data === "object") {
        const data = value.content_data,
          media = data.item_content_data || {};
        const kind =
          media.content_type || data.item_content_type || value.content_type;
        const timed =
          (media.progress_support === true ||
            media.progress_support === "true") &&
          Number.isFinite(Number(media.duration)) &&
          Number(media.duration) > 0;
        const video =
          videoTypes.has(kind) ||
          (kind === "embed" && videoSubtypes.has(media.content_subtype)) ||
          timed;
        const nonVideo =
          nonVideoTypes.has(kind) || nonVideoTypes.has(value.content_type);
        const id = String(value.module_item_id || "");
        if (video) {
          videoCount++;
          row.hasVideo = true;
          if (/^\d{1,20}$/.test(id))
            row.mediaByItem[id] = {
              video: true,
              kind: videoTypes.has(kind) ? kind : "movie",
              source_type: String(kind || "timed_media").slice(0, 64),
            };
        } else if (nonVideo) {
          if (/^\d{1,20}$/.test(id)) row.mediaByItem[id] = { video: false };
        } else if (
          value.content_type === "attendance_item" ||
          data.item_content_type === "commons" ||
          data.use_attendance === true
        ) {
          row.unsupported = true;
          log(
            "Unsupported learning content type: " +
              String(kind || "missing").slice(0, 64),
          );
        }
      }
      if (
        Object.entries(value).some(
          ([k, v]) =>
            /^(content_type|item_content_type|kind)$/.test(k) &&
            videoTypes.has(v),
        )
      )
        row.hasVideo = true;
      for (const child of Object.values(value)) walk(child, depth + 1);
    };
    walk(payload);
    row.videoCount = Math.max(row.videoCount || 0, videoCount);
    log(`LearningX ${match[1]} ${match[2]} 완료`);
    if (remaining < 0) row.failed = true;
  };
  const fetchOriginal = window.fetch.bind(window);
  window.fetch = function (...args) {
    const match = identify(args[0]),
      row = begin(match);
    if (match && typeof Headers !== "undefined") {
      try {
        rememberAuthorization(
          new Headers(args[1]?.headers || args[0]?.headers).get(
            "Authorization",
          ),
        );
      } catch {}
    }
    return fetchOriginal(...args).then(
      (response) => {
        if (row)
          response
            .clone()
            .text()
            .then(parseCampusJSON)
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
              : parseCampusJSON(this.responseText),
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
  const setHeader = XMLHttpRequest.prototype.setRequestHeader;
  if (setHeader)
    XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
      if (
        this.__calixReadMatch &&
        String(name).toLowerCase() === "authorization"
      )
        rememberAuthorization(value);
      return setHeader.call(this, name, value);
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
  const jsonRequest = async (url, headers = undefined) => {
    log(`HTTP 시작 GET ${new URL(url, location.origin).pathname}`);
    const controller = new AbortController();
    controllers.add(controller);
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetchOriginal(url, {
        credentials: "include",
        cache: "no-cache",
        headers,
        redirect: "error",
        signal: controller.signal,
      });
      log(
        `HTTP 응답 ${response.status} GET ${new URL(url, location.origin).pathname}`,
      );
      if (response.status === 401 || response.status === 403)
        throw Error("AUTH_REQUIRED");
      if (
        !response.ok ||
        !/json/i.test(response.headers.get("content-type") || "")
      )
        throw Error("HTTP_" + response.status);
      const text = await response.text();
      if (text.length > 16000000) throw Error("RESPONSE_TOO_LARGE");
      return { response, value: parseCampusJSON(text) };
    } finally {
      clearTimeout(timer);
      controllers.delete(controller);
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
  const stable = (value, depth = 0) => {
    if (depth > 32) throw Error("MANIFEST_DEPTH");
    if (Array.isArray(value)) return value.map((v) => stable(v, depth + 1));
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((k) => [k, stable(value[k], depth + 1)]),
      );
    return value;
  };
  state.videoManifest = async (course, refresh, depth = 0) => {
    if (depth > 6) return { cacheable: false };
    try {
      let data = captured.get(String(course));
      let authorization = learningAuthorization;
      if (!authorization && typeof document !== "undefined") {
        const value = document.cookie.match(
          /(?:^|;\s*)xn_api_token=([^;]+)/,
        )?.[1];
        if (value) authorization = "Bearer " + decodeURIComponent(value);
      }
      if ((!refresh && !data) || (refresh && !authorization)) {
        if (typeof document !== "undefined")
          for (const frame of document.querySelectorAll("iframe")) {
            try {
              const peer = frame.contentWindow?.[key];
              if (peer && peer !== state) {
                const value = await peer.videoManifest(
                  course,
                  refresh,
                  depth + 1,
                );
                if (value.cacheable) return value;
              }
            } catch {}
          }
        return { cacheable: false };
      }
      if (refresh) {
        data = {};
        for (const kind of ["modules", "lessons"]) {
          const url =
            `/learningx/api/v1/courses/${course}/${kind}` +
            (kind === "modules" ? "?include_detail=true" : "");
          const { response, value } = await jsonRequest(url, {
            Authorization: authorization,
          });
          if (response.headers.get("link")) return { cacheable: false };
          const rows = Array.isArray(value) ? value : value?.[kind];
          if (!Array.isArray(rows)) return { cacheable: false };
          data[kind] = value;
        }
      }
      if (!data?.modules || !data?.lessons) return { cacheable: false };
      const text = JSON.stringify({
        schema: 1,
        rules: mediaRules,
        data: stable(data),
      });
      if (text.length > 2000000) return { cacheable: false };
      // Reuse is unsafe when the API omits the student's completion status.
      const states = {};
      let complete = true;
      const inspect = (value) => {
        if (!value || typeof value !== "object") return;
        if (value.published === false) return;
        const data = value.content_data,
          media = data?.item_content_data || {};
        const kind =
          media.content_type || data?.item_content_type || value.content_type;
        const video =
          videoTypes.has(kind) ||
          (kind === "embed" && videoSubtypes.has(media.content_subtype)) ||
          (media.progress_support === true && Number(media.duration) > 0);
        if (data && video) {
          const id = String(value.module_item_id || "");
          if (
            !/^[1-9]\d{0,19}$/.test(id) ||
            typeof value.completed !== "boolean"
          )
            complete = false;
          else states[id] = value.completed;
        }
        for (const child of Object.values(value))
          if (typeof child === "object") {
            if (Array.isArray(child)) child.forEach(inspect);
            else inspect(child);
          }
      };
      inspect(data.modules);
      const hash = await crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(text),
      );
      return {
        cacheable: true,
        complete,
        states,
        digest: Array.from(new Uint8Array(hash), (n) =>
          n.toString(16).padStart(2, "0"),
        ).join(""),
      };
    } catch {
      return { cacheable: false };
    }
  };
  state.start = (id, operation, course) => {
    state.jobs = { [id]: { status: "pending" } };
    (async () => {
      if (operation === "video-probe" || operation === "video-baseline") {
        if (!Number.isSafeInteger(course) || course <= 0)
          throw Error("INVALID_COURSE");
        return state.videoManifest(course, operation === "video-probe");
      }
      if (operation === "owner") {
        const { value: profile } = await jsonRequest(
          "/api/v1/users/self/profile",
        );
        if (typeof profile.id === "number" && !Number.isSafeInteger(profile.id))
          throw Error("INVALID_OWNER");
        const owner = String(profile.id);
        if (!/^[1-9]\d{0,18}$/.test(owner)) throw Error("INVALID_OWNER");
        return { owner };
      }
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
