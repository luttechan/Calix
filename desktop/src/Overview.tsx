import { locale, t, useLanguage } from "./i18n";
import { useEffect, useMemo, useState } from "react";
import { TypeBadge, useCalix } from "./App";
import { ChevronRight, Search } from "lucide-react";
import type { EventItem } from "./types";
import { deadlineGroup, orderByDeadline } from "./overviewState";
import "./overview.css";
import { ChangedNumber } from "./ChangedNumber";
import { PlanningPanel } from "./Planning";
function Items({ items }: { items: EventItem[] }) {
  useLanguage();
  const { openEvent } = useCalix();
  return (
    <div className="overview-items">
      {items.length ? (
        items.map((item) => (
          <button
            className="overview-event"
            key={item.key}
            onClick={() => openEvent(item.key)}
          >
            <TypeBadge event={item} />
            <span className="overview-event-copy">
              <strong title={item.title}>{item.title}</strong>
              <small>{item.course_name}</small>
            </span>
            <time
              dateTime={
                item.due_at && Number.isFinite(Date.parse(item.due_at))
                  ? item.due_at
                  : undefined
              }
            >
              {item.due_at && Number.isFinite(Date.parse(item.due_at))
                ? new Date(item.due_at).toLocaleString(locale(), {
                    month: "numeric",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : t("기한 없음")}
            </time>
            <ChevronRight
              size={15}
              className="overview-chevron"
              aria-hidden="true"
            />
          </button>
        ))
      ) : (
        <p className="empty">{t("일정 없음")}</p>
      )}
    </div>
  );
}
export function DeadlinePage() {
  useLanguage();
  const { data } = useCalix();
  const [now, setNow] = useState(() => new Date()),
    [query, setQuery] = useState(""),
    [kind, setKind] = useState("all"),
    [planning, setPlanning] = useState(false),
    [planningOpened, setPlanningOpened] = useState(false);
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
    <>
      <PageHeading title={t("마감 보드")}>
        <button
          type="button"
          aria-expanded={planning}
          aria-controls="deadline-planning"
          onClick={() => {
            setPlanningOpened(true);
            setPlanning((open) => !open);
          }}
        >{t("학습 계획")}{" "}<ChevronRight size={16} aria-hidden="true" />
        </button>
      </PageHeading>
    <section className="overview-page">
      <div id="deadline-planning" hidden={!planning}>
        {planningOpened && <PlanningPanel now={now} />}
      </div>
      <div className="deadline-list">
        <div className="deadline-filters">
          <label className="deadline-search">
            <Search size={16} aria-hidden="true" />
            <input
              aria-label={t("마감 일정 검색")}
              placeholder={t("일정, 과목 검색")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <select
            aria-label={t("일정 종류")}
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="all">{t("전체 유형")}</option>
            <option value="assignment">{t("과제")}</option>
            <option value="movie">{t("영상")}</option>
          </select>
        </div>
        {[
          ["overdue", "기한 경과"],
          ["today", "오늘"],
          ["week", "7일 이내"],
          ["later", "이후"],
          ["undated", "기한 없음"],
        ].map(([id, label]) => {
          const selected = items.filter((e) => deadlineGroup(e, now) === id);
          if (!selected.length) return null;
          return (
            <section key={id} className={`deadline-group ${id}`}>
              <h2>
                {t(label)}
                <ChangedNumber value={selected.length} />
              </h2>
              <Items items={selected} />
            </section>
          );
        })}
        {!items.length && (
          <p className="deadline-empty" role="status">
            {query.trim() || kind !== "all"
              ? t("검색 결과 없음")
              : t("남은 일정 없음")}
          </p>
        )}
      </div>
    </section>
    </>
  );
}
export function CourseOverviewPage() {
  useLanguage();
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
    <>
    <PageHeading title={t("과목별 현황")} />
    <section className="overview-page">
      <div className="overview-tools">
        <input
          aria-label={t("과목 검색")}
          placeholder={t("과목 검색")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <label className="overview-checkbox">
          <input
            type="checkbox"
            checked={onlyPending}
            onChange={(e) => setOnlyPending(e.target.checked)}
          />{t("미완료 있는 과목")}{" "}</label>
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
                <span className="type-badge assignment">{t("과제")}{" "}<ChangedNumber value={pending.filter((e) => e.kind === "assignment").length} />
                </span>
                <span className="type-badge movie">{t("영상")}{" "}<ChangedNumber value={pending.filter((e) => e.kind === "movie").length} />
                </span>
                <span>{t("완료")}{" "}<ChangedNumber value={`${done}/${course.items.length}`} />
                </span>
              </div>
              <progress
                aria-label={t("{0} 완료율", [String(course.name)])}
                max={100}
                value={percent}
              />
              {pending.length > 0 && (
                <details>
                  <summary>{t("미완료 일정")}{" "}{pending.length}{t("개")}</summary>
                  <Items items={pending} />
                </details>
              )}
            </article>
          );
        })}
      </div>
      {!groups.length && <p className="empty">{t("과목 없음")}</p>}
    </section>
    </>
  );
}
import { PageHeading } from "./PageHeading";
