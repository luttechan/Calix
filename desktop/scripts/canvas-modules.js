(() => {
  if (location.origin !== "https://canvas.bufs.ac.kr") return;
  const key = Symbol.for("calix.canvas.modules");
  if (window[key]) return;
  const controllers = new Set();
  let epoch = 0;
  const reader = {
    cancel() {
      epoch++;
      for (const c of controllers) c.abort();
      controllers.clear();
    },
  };
  window[key] = reader;
  const positive = (v) => (typeof v === "number" || (typeof v === "string" && /^[1-9]\d*$/.test(v))) && Number.isSafeInteger(Number(v)) && Number(v) > 0;
  const learningx = (v) =>
    /LearningX|주차학습|학습콘텐츠|강의콘텐츠|온라인강의|\/learningx\//i.test(
      String(v || ""),
    );
  const videoUrl = (value) => {
    try {
      const u = new URL(value, location.origin);
      return (
        ["http:", "https:"].includes(u.protocol) &&
        (/\.(mp4|webm|mov|m4v|m3u8|mp3|m4a|ogg)(?:$)/i.test(u.pathname) ||
          /(^|\.)(youtube\.com|youtu\.be|vimeo\.com)$/.test(u.hostname) ||
          /\/media_objects\//.test(u.pathname))
      );
    } catch {
      return false;
    }
  };
  reader.collect = async (course) => {
    if (!positive(course)) throw Error("INVALID_COURSE");
    reader.assignmentIds = {};
    const generation = epoch,
      deadline = Date.now() + 12000,
      warnings = new Set(),
      memo = new Map();
    const result = {
      status: "available",
      complete: true,
      items: [],
      assignment_ids: [],
      learningx: { present: null, url: null },
      warnings: [],
    };
    const check = () => {
      if (generation !== epoch) throw Error("CANCELLED");
      if (Date.now() >= deadline) throw Error("MODULE_TIMEOUT");
    };
    const request = async (path, max = 5000) => {
      check();
      const url = new URL(path, location.origin);
      if (
        url.origin !== location.origin ||
        !url.pathname.startsWith(`/api/v1/courses/${course}/`)
      )
        throw Error("UNSAFE_MODULE_URL");
      const c = new AbortController();
      controllers.add(c);
      const timer = setTimeout(
        () => c.abort(),
        Math.max(1, Math.min(max, deadline - Date.now())),
      );
      try {
        const response = await fetch(url, {
          credentials: "include",
          cache: "no-cache",
          redirect: "error",
          signal: c.signal,
        });
        if (response.status === 401) throw Error("AUTH_REQUIRED");
        if (!response.ok) throw Error("HTTP_" + response.status);
        if (!/json/i.test(response.headers.get("content-type") || ""))
          throw Error("INVALID_MODULE_JSON");
        const text = await response.text();
        if (text.length > 2000000) throw Error("MODULE_RESPONSE_TOO_LARGE");
        const value = JSON.parse(
          text.trimStart().replace(/^while\s*\(\s*1\s*\)\s*;/, ""),
        );
        check();
        return { value, response };
      } catch (error) {
        if (error.name === "AbortError")
          throw Error(generation !== epoch ? "CANCELLED" : "MODULE_TIMEOUT");
        throw error;
      } finally {
        clearTimeout(timer);
        controllers.delete(c);
      }
    };
    const list = async (path, params = {}, max = 5000) => {
      let url = new URL(path, location.origin);
      for (const [k, v] of Object.entries(params))
        for (const x of Array.isArray(v) ? v : [v])
          url.searchParams.append(k, x);
      const expected = url.pathname,
        seen = new Set(),
        rows = [];
      for (let page = 0; page < 1000; page++) {
        check();
        if (
          url.origin !== location.origin ||
          url.pathname !== expected ||
          seen.has(url.href)
        )
          throw Error("UNSAFE_MODULE_PAGE");
        seen.add(url.href);
        const { value, response } = await request(url, max);
        if (!Array.isArray(value)) throw Error("INVALID_MODULE_LIST");
        rows.push(...value);
        if (rows.length > 10000) throw Error("TOO_MANY_MODULE_ITEMS");
        const next = (response.headers.get("link") || "")
          .split(",")
          .find((v) => /;\s*rel=["']?next["']?(?:;|$)/i.test(v));
        if (!next) return rows;
        const match = next.trim().match(/^<([^>]+)>/);
        if (!match) throw Error("INVALID_MODULE_PAGE");
        url = new URL(match[1], url);
      }
      throw Error("TOO_MANY_MODULE_PAGES");
    };
    const details = (path) => {
      if (!memo.has(path))
        memo.set(
          path,
          request(path).then((r) => r.value),
        );
      return memo.get(path);
    };
    const pool = async (rows, work) => {
      let index = 0;
      await Promise.all(
        Array.from({ length: Math.min(4, rows.length) }, async () => {
          while (index < rows.length) {
            const row = rows[index++];
            try {
              check();
              await work(row);
            } catch (error) {
              if (
                error.message === "AUTH_REQUIRED" ||
                error.message === "CANCELLED"
              )
                throw error;
              result.complete = false;
              warnings.add(
                error.message === "MODULE_TIMEOUT"
                  ? "모듈 응답 시간 초과"
                  : "일부 모듈 자료 확인 필요",
              );
            }
          }
        }),
      );
    };
    const base = `/api/v1/courses/${course}`;
    const tabsPromise = list(base + "/tabs", {}, 3000)
      .then((tabs) => {
        const candidates = tabs.filter(
          (t) => t.hidden !== true && learningx(t.label),
        );
        result.learningx.present =
          candidates.length > 0 || result.learningx.present === true;
        const entry = candidates.find((t) => {
          try {
            const u = new URL(t.html_url, location.origin);
            return (
              u.origin === location.origin &&
              new RegExp(`^/courses/${course}/external_tools/\\d+`).test(
                u.pathname,
              )
            );
          } catch {
            return false;
          }
        });
        if (entry)
          result.learningx.url = new URL(entry.html_url, location.origin).href;
      })
      .catch((error) => {
        if (["AUTH_REQUIRED", "CANCELLED"].includes(error.message)) throw error;
      });
    void tabsPromise.catch(() => {});
    try {
      let modules;
      try {
        modules = await list(base + "/modules", {
          "include[]": ["items", "content_details"],
          per_page: 100,
        });
      } catch (error) {
        if (error.message === "HTTP_404") {
          result.status = "missing";
          modules = [];
        } else throw error;
      }
      const items = new Map();
      await pool(modules, async (module) => {
        if (module.published === false) return;
        if (!positive(module.id)) throw Error("INVALID_MODULE_ID");
        let rows = module.items;
        if (
          !Array.isArray(rows) ||
          !Number.isSafeInteger(module.items_count) ||
          rows.length < module.items_count
        )
          rows = await list(base + `/modules/${module.id}/items`, {
            "include[]": ["content_details"],
            per_page: 100,
          });
        if (
          !Array.isArray(rows) ||
          (Number.isSafeInteger(module.items_count) &&
            rows.length < module.items_count)
        )
          throw Error("INCOMPLETE_MODULE_ITEMS");
        for (const item of rows) {
          if (item.published === false) continue;
          if (!positive(item.id)) throw Error("INVALID_MODULE_ITEM");
          const previous = items.get(Number(item.id));
          if (
            previous &&
            JSON.stringify(previous.item) !== JSON.stringify(item)
          )
            throw Error("CONFLICTING_MODULE_ITEM");
          items.set(Number(item.id), {
            item,
            week: String(module.name || "").slice(0, 200),
          });
        }
      });
      await pool([...items.values()], async ({ item, week }) => {
        if (item.type === "Assignment") {
          if (!positive(item.content_id)) throw Error("INVALID_ASSIGNMENT_ID");
          result.assignment_ids.push(Number(item.content_id));
          return;
        }
        if (["SubHeader", "Quiz", "Discussion"].includes(item.type)) return;
        let video = false,
          source_id = item.id,
          source_kind = String(item.type || "").toLowerCase();
        if (item.type === "ExternalTool") {
          const label = item.title + " " + item.external_url;
          if (learningx(label)) {
            result.learningx.present = true;
            if (!result.learningx.url && positive(item.content_id))
              result.learningx.url =
                location.origin +
                `/courses/${course}/external_tools/${item.content_id}`;
            return;
          }
          if (!videoUrl(item.external_url)) {
            result.complete = false;
            warnings.add("외부 도구 자료 확인 필요");
            return;
          }
          video = true;
        } else if (item.type === "ExternalUrl")
          video = videoUrl(item.external_url);
        else if (item.type === "File") {
          if (!positive(item.content_id)) throw Error("INVALID_FILE_ID");
          const file = await details(base + `/files/${item.content_id}`);
          source_id = item.content_id;
          video =
            /^(video|audio)\//i.test(file["content-type"] || "") ||
            ["video", "audio"].includes(file.mime_class);
        } else if (item.type === "Page") {
          if (
            typeof item.page_url !== "string" ||
            !item.page_url ||
            item.page_url.length > 500
          )
            throw Error("INVALID_PAGE_ID");
          const page = await details(
            base + "/pages/" + encodeURIComponent(item.page_url),
          );
          if (typeof page.body !== "string")
            throw Error("PAGE_BODY_UNAVAILABLE");
          if (page.body.length > 500000) throw Error("PAGE_TOO_LARGE");
          source_id = positive(page.page_id) ? Number(page.page_id) : item.id;
          const urls = [
            ...page.body.matchAll(/(?:src|href)\s*=\s*["']([^"']+)["']/gi),
          ].map((m) => m[1].replace(/&amp;/g, "&"));
          video =
            /<video\b|data-media-id\s*=/i.test(page.body) ||
            urls.some(videoUrl);
          if (urls.some(learningx)) {
            result.learningx.present = true;
          }
          if (!video && /<iframe\b/i.test(page.body) && !urls.some(learningx)) {
            result.complete = false;
            warnings.add("페이지의 외부 자료 확인 필요");
          }
        } else {
          result.complete = false;
          warnings.add("미지원 모듈 항목");
          return;
        }
        if (!video) return;
        const requirement = item.completion_requirement,
          done =
            typeof requirement?.completed === "boolean"
              ? requirement.completed
              : null;
        result.items.push({
          id: Number(item.id),
          source_id: Number(source_id),
          source_kind,
          title: String(item.title || "").slice(0, 1000),
          url: location.origin + `/courses/${course}/modules/items/${item.id}`,
          week,
          completed: done,
          content_details: item.content_details || {},
        });
      });
    } catch (error) {
      if (["AUTH_REQUIRED", "CANCELLED"].includes(error.message)) {
        reader.cancel();
        await tabsPromise.catch(() => {});
        throw error;
      }
      result.status = "unavailable";
      result.complete = false;
      warnings.add(
        error.message === "MODULE_TIMEOUT"
          ? "모듈 응답 시간 초과"
          : "모듈 목록 확인 필요",
      );
    }
    await tabsPromise;
    result.items.sort((a, b) => a.id - b.id);
    result.assignment_ids = [...new Set(result.assignment_ids)].sort(
      (a, b) => a - b,
    );
    reader.assignmentIds = { [course]: result.assignment_ids };
    result.warnings = [...warnings].slice(0, 6);
    return result;
  };
})();
