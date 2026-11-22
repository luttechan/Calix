import { t, useLanguage } from "./i18n";
import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Search, CalendarDays } from "lucide-react";
import { rpc, subscribe } from "./bridge";
import { useCalix } from "./App";
import { dueText } from "./dates";

export type AttendanceRow = {
  key: string;
  course_id: number;
  course_name: string;
  week: number | null;
  lesson: number | null;
  date: string;
  start_at: string;
  due_at: string;
  title: string;
  source: string;
  kind: string;
  status: string;
  stale: boolean;
  updated_at: string;
};
const labels: Record<string, string> = {
  attendance: "출석",
  late: "지각",
  absent: "결석",
  excused: "공결",
  none: "미확인",
  unknown: "미확인",
};
export function AttendancePage() {
  useLanguage();
  const { data, notify, soundError } = useCalix();
  const [rows, setRows] = useState<AttendanceRow[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [course, setCourse] = useState(""),
    [view, setView] = useState("date"),
    [source, setSource] = useState("canvas"),
    [query, setQuery] = useState("");
  useEffect(() => {
    let alive = true,
      sequence = 0;
    const load = () => {
      const id = ++sequence;
      setLoading(true);
      void rpc<AttendanceRow[]>("attendance.read")
        .then((r) => {
          if (alive && sequence === id) {
            setRows(r);
            setError("");
          }
        })
        .catch((e) => {
          if (alive && sequence === id) {
            setError(String(e));
            soundError();
          }
        })
        .finally(() => {
          if (alive && sequence === id) setLoading(false);
        });
    };
    load();
    const off = subscribe((e) => {
      if (e.event === "data-changed") load();
    });
    return () => {
      alive = false;
      off();
    };
  }, []);
  const selected = useMemo(() => {
    const coursesWithItems = new Set(
      rows.filter((row) => row.source === "item").map((row) => row.course_id),
    );
    const search = query.trim().toLowerCase();
    return rows
        .filter(
          (r) =>
            (!course || String(r.course_id) === course) &&
            r.source === (source === "canvas"
              ? (coursesWithItems.has(r.course_id) ? "item" : "lesson")
              : source) &&
            `${r.title} ${r.course_name}`
              .toLowerCase()
              .includes(search),
        )
        .sort((a, b) =>
          view === "date"
            ? (a.date || a.start_at || "9999").localeCompare(
                b.date || b.start_at || "9999",
              ) || a.course_name.localeCompare(b.course_name)
            : a.course_name.localeCompare(b.course_name) ||
              (view === "lesson"
                ? (a.lesson ?? 999) - (b.lesson ?? 999) ||
                  (a.week ?? 999) - (b.week ?? 999)
                : (a.week ?? 999) - (b.week ?? 999) ||
                  (a.lesson ?? 999) - (b.lesson ?? 999)),
        );
  }, [rows, course, view, source, query]);
  return (
    <section className="learning-page">
      <div className="page-heading">
        <div>
          <h1>{t("출결 현황")}</h1>
        </div>
        <button
          onClick={() => void rpc("sync").catch((e) => notify(String(e), true))}
        >
          <RefreshCw size={16} />{t("동기화")}{" "}</button>
      </div>
      <div className="glass learning-toolbar">
        <label className="search">
          <Search size={16} />
          <input
            aria-label={t("출결 검색")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("수업 검색")}
          />
        </label>
        <select
          aria-label={t("출결 과목")}
          value={course}
          onChange={(e) => setCourse(e.target.value)}
        >
          <option value="">{t("전체 과목")}</option>
          {data.courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          aria-label={t("출결 항목")}
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          <option value="canvas">{t("Canvas 기준")}</option>
          <option value="lesson">{t("수업별")}</option>
          <option value="item">{t("활동별")}</option>
        </select>
        <select
          aria-label={t("출결 정렬")}
          value={view}
          onChange={(e) => setView(e.target.value)}
        >
          <option value="date">{t("일자순")}</option>
          <option value="week">{t("주차순")}</option>
          <option value="lesson">{t("차시순")}</option>
        </select>
      </div>
      {error && <p role="alert">{error}</p>}
      {rows.some((r) => r.stale) && (
        <p className="attendance-warning">{t("일부 출결 갱신 필요")}{" "}</p>
      )}
      <div className="attendance-summary">
        {["attendance", "excused", "late", "absent", "none"].map((s) => (
          <div className={`glass attendance-total ${s}`} key={s}>
            <span>{t(labels[s])}</span>
            <strong>
              {
                selected.filter((r) =>
                  s === "none"
                      ? ["none", "unknown"].includes(r.status)
                      : r.status === s,
                ).length
              }
            </strong>
          </div>
        ))}
      </div>
      <div className="glass attendance-table">
        <table>
          <thead>
            <tr>
              <th>{t("일자")}</th>
              <th>{t("수업")}</th>
              <th>{t("주차 / 차시")}</th>
              <th>{t("항목")}</th>
              <th>{t("출결")}</th>
            </tr>
          </thead>
          <tbody>
            {selected.map((r) => (
              <tr key={r.key}>
                <td>
                  {r.date ? (
                    r.date.slice(0, 10)
                  ) : r.start_at ? (
                    <>
                      {r.start_at.slice(0, 10)}
                      <small>{t("수강 시작")}</small>
                    </>
                  ) : (
                    t("일자 미지정")
                  )}
                </td>
                <td>{r.course_name}</td>
                <td>
                  {r.week === null ? "—" : t("{0}주차", [String(r.week)])}
                  {r.lesson !== null ? t(" / {0}차시", [r.lesson]) : ""}
                </td>
                <td>
                  {r.title}
                  {r.source === "item" && r.due_at && (
                    <small>{t("마감")}{" "}{dueText(r.due_at)}</small>
                  )}
                </td>
                <td>
                  <span className={`attendance-status ${r.status}`}>
                    {t(labels[r.status] || "미확인")}
                  </span>
                  {r.stale && <small>{t("이전 결과")}</small>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!selected.length && (
          <div className="empty">
            <CalendarDays size={32} />
            <p>{loading ? t("출결을 불러오는 중") : t("출결 기록 없음")}</p>
          </div>
        )}
      </div>
    </section>
  );
}
