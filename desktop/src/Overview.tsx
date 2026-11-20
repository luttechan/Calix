import { useEffect, useMemo, useState } from "react";
import { useCalix } from "./App";
import type { EventItem } from "./types";
import { deadlineGroup, orderByDeadline } from "./overviewState";
import "./overview.css";
import { PlanningPanel } from "./Planning";
function Items({ items }: { items: EventItem[] }) {
  const { openEvent } = useCalix();
  return (
    <div className="overview-items">
      {items.length ? (
        items.map((item) => (
          <button key={item.key} onClick={() => openEvent(item.key)}>
            <span
              className="overview-type"
              style={{ borderColor: item.type_color }}
            >
              {item.type_name ||
                { assignment: "과제", movie: "영상" }[item.kind] ||
                "일정"}
            </span>
            <span>
              <strong>{item.title}</strong>
              <small>{item.course_name}</small>
            </span>
            <time>
              {item.due_at && Number.isFinite(Date.parse(item.due_at))
                ? new Date(item.due_at).toLocaleString("ko-KR", {
                    month: "numeric",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "기한 없음"}
            </time>
          </button>
        ))
      ) : (
        <p className="empty">일정이 없습니다.</p>
      )}
    </div>
  );
}
export function DeadlinePage() {
  const { data } = useCalix();
  const [now, setNow] = useState(() => new Date()),
    [query, setQuery] = useState(""),
    [kind, setKind] = useState("all");
  useEffect(() => {
    const update = () => setNow(new Date());
    const timer = setInterval(update, 30000);
    window.addEventListener("focus", update);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", update);
    };
  }, []);
  const items = useMemo(
    () =>
      orderByDeadline(
        data.events.filter(
          (e) =>
            !e.completed &&
            (kind === "all" || e.kind === kind) &&
            (e.title + " " + e.course_name)
              .toLocaleLowerCase()
              .includes(query.trim().toLocaleLowerCase()),
        ),
      ),
    [data.events, kind, query],
  );
  return (
    <section className="overview-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">DEADLINES</p>
          <h1>마감 보드</h1>
        </div>
      </header>
      <PlanningPanel now={now} />
      <div className="overview-tools">
        <input
          aria-label="마감 일정 검색"
          placeholder="일정·과목 검색"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          aria-label="일정 종류"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="all">전체</option>
          <option value="assignment">과제</option>
          <option value="movie">영상</option>
        </select>
      </div>
      <div className="deadline-grid">
        {[
          ["overdue", "기한 경과"],
          ["today", "오늘"],
          ["week", "7일 이내"],
          ["later", "이후"],
          ["undated", "기한 없음"],
        ].map(([id, label]) => {
          const selected = items.filter((e) => deadlineGroup(e, now) === id);
          return (
            <article key={id} className={`overview-card ${id}`}>
              <h2>
                {label}
                <span>{selected.length}</span>
              </h2>
              <Items items={selected} />
            </article>
          );
        })}
      </div>
    </section>
  );
}
export function CourseOverviewPage() {
  const { data } = useCalix();
  const [query, setQuery] = useState(""),
    [onlyPending, setOnlyPending] = useState(false);
  const groups = useMemo(() => {
    const names = new Map(data.courses.map((c) => [c.id, c.name]));
    data.events.forEach((e) => {
      if (!names.has(e.course_id))
        names.set(e.course_id, e.course_name || "개인 일정");
    });
    return [...names]
      .map(([id, name]) => ({
        id,
        name,
        items: orderByDeadline(data.events.filter((e) => e.course_id === id)),
      }))
      .filter(
        (c) =>
          c.name
            .toLocaleLowerCase()
            .includes(query.trim().toLocaleLowerCase()) &&
          (!onlyPending || c.items.some((e) => !e.completed)),
      )
      .sort((a, b) => a.name.localeCompare(b.name, "ko"));
  }, [data.courses, data.events, query, onlyPending]);
  return (
    <section className="overview-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">COURSES</p>
          <h1>과목별 현황</h1>
        </div>
      </header>
      <div className="overview-tools">
        <input
          aria-label="과목 검색"
          placeholder="과목 검색"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <label>
          <input
            type="checkbox"
            checked={onlyPending}
            onChange={(e) => setOnlyPending(e.target.checked)}
          />
          미완료 있는 과목
        </label>
      </div>
      <div className="deadline-grid">
        {groups.map((course) => {
          const pending = course.items.filter((e) => !e.completed),
            done = course.items.length - pending.length,
            percent = course.items.length
              ? Math.round((done / course.items.length) * 100)
              : 0;
          return (
            <article className="overview-card" key={course.id}>
              <h2>{course.name}</h2>
              <div className="course-counts">
                <span>
                  과제 {pending.filter((e) => e.kind === "assignment").length}
                </span>
                <span>
                  영상 {pending.filter((e) => e.kind === "movie").length}
                </span>
                <span>
                  완료 {done}/{course.items.length}
                </span>
              </div>
              <progress
                aria-label={`${course.name} 완료율`}
                max={100}
                value={percent}
              />
              <details>
                <summary>미완료 일정 {pending.length}개</summary>
                <Items items={pending} />
              </details>
            </article>
          );
        })}
      </div>
      {!groups.length && <p className="empty">과목이 없습니다.</p>}
    </section>
  );
}
