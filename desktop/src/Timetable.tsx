import { semesterName, t, useLanguage } from "./i18n";
import { PageHeading } from "./PageHeading";
import { ColorField } from "./ColorField";
import {sessionLanes} from "./planningState";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type RefObject } from "react";
import { Plus, Sun, Trash2, Monitor, ArrowUpRight, Paintbrush, Sparkles, Maximize2, Minimize2, CalendarRange, Ruler, Pencil, Check } from "lucide-react";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Modal, TypeBadge, useCalix } from "./App";
import { weekdays, dueText, status } from "./dates";
import { useTimetableScale } from "./useTimetableScale";
import { TimeField } from "./TimeField";
import { ChangedNumber } from "./ChangedNumber";
import { TimetableThemePicker } from "./TimetableThemePicker";
import type { Session, TimetableAppearance, TimetableColors } from "./types";
import { automaticTimetableAppearance, defaultTimetableColors, matchingTimetableTheme, timetableCourseColor, timetableCourseKey, timetablePalette, timetableThemes } from "./timetableThemes";

const minute = (value: string) => {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
};
function TimetableColorDialog({ appearance, palette, courses, presets, pending, onSave, onClose }: {
  appearance: TimetableAppearance;
  palette: string[];
  courses: { session: Session; title: string }[];
  presets: TimetableColors["presets"];
  pending: boolean;
  onSave: (style: TimetableAppearance, name?: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [saveTheme, setSaveTheme] = useState(false);
  const [colors, setColors] = useState(() => appearance.mode === "manual"
    ? Object.fromEntries(courses.map(({ session }, index) => [timetableCourseKey(session), timetableCourseColor(session, index % 8, appearance, palette)]))
    : appearance.mode === "custom" ? appearance.colors : {});
  const draft: TimetableAppearance = { ...appearance, mode: "custom", colors, slots: appearance.mode === "custom" ? appearance.slots : [] };
  const label = name.trim();
  return <Modal title={t("시간표 색상")} onClose={() => { if (!pending) onClose(); }}>
    <form className="timetable-color-form" onSubmit={event => {
      event.preventDefault();
      if (saveTheme) {
        const slots = palette.map((color, index) => courses[index]
          ? timetableCourseColor(courses[index].session, index, draft, palette)
          : draft.slots[index] || color);
        onSave({ ...draft, slots }, label);
      } else {
        onSave(draft);
      }
    }}>
      <div className="timetable-course-colors">
        {courses.map(({ session, title }, index) => {
          const key = timetableCourseKey(session);
          return <div className="timetable-course-color" key={key}>
            <span>{title}</span>
            <ColorField label={title} value={timetableCourseColor(session, index % 8, draft, palette)}
              disabled={pending} onChange={value => setColors(previous => ({ ...previous, [key]: value }))} />
          </div>;
        })}
      </div>
      {saveTheme && <label>{t("테마 이름")}<input autoFocus required maxLength={32}
        value={name} onChange={event => setName(event.target.value)} disabled={pending} /></label>}
      <div className="dialog-actions">
        {!saveTheme && <button type="button" disabled={pending} onClick={() => setSaveTheme(true)}>{t("테마로 저장")}</button>}
        {saveTheme && <button type="button" disabled={pending} onClick={() => setSaveTheme(false)}>{t("취소")}</button>}
        <button type="submit" className="primary" disabled={pending ||
          (saveTheme && (!label || (!Object.hasOwn(presets, label) && Object.keys(presets).length >= 24)))}>
          {t(saveTheme ? "저장 및 적용" : "적용")}
        </button>
      </div>
    </form>
  </Modal>;
}

export type TimetableViewState = {
  mainTerm: string;
  semester: string;
  days: number;
  density: number;
  scrollLeft: number;
  scrollTop: number;
};

export function TimetablePage({ onOpenHome, viewState }: {
  onOpenHome: () => void;
  viewState: RefObject<TimetableViewState | null>;
}) {
  useLanguage();
  const { data, mutate } = useCalix();
  const previousView = viewState.current?.mainTerm === data.mainTerm ? viewState.current : null;
  const [now, setNow] = useState(Date.now);
  const [days, setDays] = useState(previousView?.days ?? 5);
  const [expanded, setExpanded] = useState(false);
  const windowActions = useRef(Promise.resolve());
  useEffect(() => {
    if (!expanded) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented && !document.querySelector("dialog[open]")) {
        setExpanded(false);
      }
    };
    window.addEventListener("keydown", escape);
    const appWindow = isTauri() ? getCurrentWindow() : null;
    let active = true;
    let maximizedHere = false;
    if (appWindow) {
      windowActions.current = windowActions.current.then(async () => {
        if (await appWindow.isMaximized() || !active) return;
        await appWindow.maximize();
        maximizedHere = true;
      }).catch(() => {});
    }
    return () => {
      active = false;
      window.removeEventListener("keydown", escape);
      if (appWindow) {
        windowActions.current = windowActions.current.then(async () => {
          if (maximizedHere && await appWindow.isMaximized()) await appWindow.unmaximize();
        }).catch(() => {});
      }
    };
  }, [expanded]);
  const [density, setDensity] = useState(previousView?.density ?? 0);
  const [densityDialog, setDensityDialog] = useState(false);
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [semester, setSemester] = useState(previousView?.semester ?? data.mainTerm);
  const [viewing, setViewing] = useState<Session | null>(null);
  const term =
    data.timetableTerms.find((t) => t.name === semester) ??
    data.timetableTerms.find((t) => t.name === data.mainTerm) ??
    { name: data.mainTerm, offDays: [] };
  const offDays = term.offDays;
  const sessions = useMemo(() => data.sessions.filter(s => s.semester === term.name), [data.sessions, term.name]);
  const colors = data.preferences.timetable_colors ?? defaultTimetableColors;
  const recommendation = matchingTimetableTheme[data.preferences.theme] ?? 0;
  const appearance = colors.terms[term.name] ?? colors.base;
  const selectedPreset = useMemo(() => {
    if (appearance.mode !== "custom") return "";
    const value = JSON.stringify(appearance);
    return Object.entries(colors.presets).find(([, preset]) => JSON.stringify(preset) === value)?.[0] ?? "";
  }, [appearance, colors.presets]);
  const palette = useMemo(() => timetablePalette(appearance.theme), [appearance.theme]);
  const theme = timetableThemes[appearance.theme];
  const [colorDialog, setColorDialog] = useState(false);
  const [colorPending, setColorPending] = useState(false);
  const courseList = useMemo(() => {
    const courses = new Map<string, Session>();
    for (const session of [...sessions].sort((a, b) => a.id - b.id)) {
      const key = timetableCourseKey(session);
      if (!courses.has(key)) courses.set(key, session);
    }
    return [...courses.values()];
  }, [sessions]);
  const courseSlots = useMemo(() => new Map(courseList.map((course, index) =>
    [timetableCourseKey(course), index % 8])), [courseList]);
  const sessionColor = (session: Session) =>
    timetableCourseColor(session, courseSlots.get(timetableCourseKey(session)) ?? 0, appearance, palette);
  const saveAppearance = async (style: TimetableAppearance, preset?: string) => {
    if (colorPending) return;
    setColorPending(true);
    try {
      await mutate("timetable.colors", {
        ...colors, terms: { ...colors.terms, [term.name]: style },
        presets: preset ? { ...colors.presets, [preset]: style } : colors.presets,
      });
      setColorDialog(false);
    } finally {
      setColorPending(false);
    }
  };
  const choose = (s: Session) => (mode === "edit" ? setEdit(s) : setViewing(s));
  const [edit, setEdit] = useState<Session | null | undefined>();
  const [off, setOff] = useState(false);
  const [selectedDays, setSelectedDays] = useState(offDays);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const scheduled = useMemo(() => sessions.filter(s => !s.is_online), [sessions]);
  const online = useMemo(() => sessions.filter(s => s.is_online), [sessions]);
  const start = Math.min(
    480,
    ...scheduled.map((s) => Math.floor(minute(s.start_time) / 60) * 60),
  );
  const end = Math.max(
    1140,
    ...scheduled.map((s) => Math.ceil(minute(s.end_time) / 60) * 60),
  );
  const { panel, unit, height } = useTimetableScale(
    start,
    end,
    data.timetableConfigured,
    density,
    online.length > 0,
  );
  useLayoutEffect(() => {
    const saved = viewState.current;
    const element = panel.current;
    if (!element) return;
    const sameSemester = saved?.mainTerm === data.mainTerm && saved.semester === term.name;
    element.scrollTo({ left: sameSemester ? saved.scrollLeft : 0, top: sameSemester ? saved.scrollTop : 0, behavior: "instant" });
  }, [data.mainTerm, data.timetableConfigured, panel, term.name, viewState]);
  useLayoutEffect(() => {
    if (!data.timetableConfigured) return;
    const saved = viewState.current;
    const sameSemester = saved?.mainTerm === data.mainTerm && saved.semester === term.name;
    viewState.current = {
      mainTerm: data.mainTerm, semester: term.name, days, density,
      scrollLeft: sameSemester ? saved.scrollLeft : 0,
      scrollTop: sameSemester ? saved.scrollTop : 0,
    };
  }, [data.mainTerm, data.timetableConfigured, days, density, term.name, viewState]);
  // Leave room for a readable, clickable card even for short custom sessions.
  const minimumCardHeight = 24;
  const gridHeight = Math.max(height, ...scheduled.map(session =>
    ((minute(session.start_time) - start) / 60) * unit + minimumCardHeight + 3));
  const laneMinutes = Math.ceil((minimumCardHeight / unit) * 60);
  const lanes = useMemo(() => sessionLanes(scheduled, laneMinutes), [scheduled, laneMinutes]);
  const { workloads, nextDeadline } = useMemo(() => {
    const counts = new Map<number, { assignment: number; movie: number }>();
    let next = Infinity;
    for (const event of data.events) {
      if (event.completed || (event.kind !== "assignment" && event.kind !== "movie")) continue;
      const deadline = event.due_at ? Date.parse(event.due_at) : Infinity;
      if (deadline <= now) continue;
      if (deadline < next) next = deadline;
      const row = counts.get(event.course_id) || { assignment: 0, movie: 0 };
      row[event.kind]++;
      counts.set(event.course_id, row);
    }
    return { workloads: counts, nextDeadline: next };
  }, [data.events, now]);
  useEffect(() => {
    const update = () => setNow(Date.now());
    const timer = Number.isFinite(nextDeadline)
      ? setTimeout(update, Math.max(1, Math.min(nextDeadline - Date.now(), 2 ** 31 - 1))) : undefined;
    window.addEventListener("focus", update);
    return () => { clearTimeout(timer); window.removeEventListener("focus", update); };
  }, [nextDeadline, now]);
  const name = (s: Session) =>
    s.title || data.courses.find((c) => c.id === s.course_id)?.name || "수업";
  const work = (s: Session) => {
    const count = workloads.get(s.course_id) || { assignment: 0, movie: 0 };
    return (
      s.course_id > 0 && (
        <div className="session-work">
          <span>{t("과제")}{" "}<ChangedNumber value={count.assignment} /></span>
          <span>{t("영상")}{" "}<ChangedNumber value={count.movie} /></span>
        </div>
      )
    );
  };
  return (
    <section className="timetable-page" data-expanded={expanded || undefined}>
      <PageHeading title={t("시간표")}>
        {data.timetableConfigured && <div className="timetable-strip">
          <select className="timetable-term-select" aria-label={t("시간표 학기")} value={term.name}
            onChange={event => {
              setSemester(event.target.value);
              setColorDialog(false);
              setViewing(null);
              setEdit(undefined);
              setOff(false);
            }}>
            {data.timetableTerms.map(termOption => <option key={termOption.name} value={termOption.name}>
              {semesterName(termOption.name)}{termOption.name === data.mainTerm ? t(" (메인)") : ""}
            </option>)}
          </select>
          <div className="timetable-tools" role="group" aria-label={t("시간표")}>
            <button type="button" className="icon-button" aria-pressed={days === 7}
              aria-label={t("주간")} data-tooltip={t(days === 7 ? "주중만 보기" : "주간 보기")}
              onClick={() => setDays(days === 5 ? 7 : 5)}><CalendarRange size={17} /></button>
            <button type="button" className="icon-button" aria-haspopup="dialog"
              aria-label={t("시간표 시간 간격")} data-tooltip={t("시간 간격")}
              onClick={() => setDensityDialog(true)}><Ruler size={17} /></button>
            <TimetableThemePicker key={term.name} style={appearance} recommended={recommendation} presets={colors.presets}
              selectedPreset={selectedPreset} pending={colorPending} onSelect={saveAppearance} />
            <button type="button" className="icon-button"
              aria-pressed={appearance.mode === "auto" && appearance.theme === recommendation} disabled={colorPending}
              aria-label={t("추천 색상 적용")} data-tooltip={t("추천 색상 적용")}
              onClick={() => {
                void saveAppearance(automaticTimetableAppearance(recommendation)).catch(() => {});
              }}><Sparkles size={17} /></button>
            <button type="button" className="icon-button" aria-haspopup="dialog" disabled={colorPending}
              aria-label={t("시간표 색상")} data-tooltip={t("시간표 색상")}
              onClick={() => setColorDialog(true)}><Paintbrush size={17} /></button>
          </div>
          <div className="timetable-tools" role="group" aria-label={t("시간표 모드")}>
            <button type="button" className="icon-button" aria-pressed={mode === "edit"}
              aria-label={t("편집 모드")} data-tooltip={t(mode === "edit" ? "편집 완료" : "편집 모드")}
              onClick={() => {
                if (mode === "edit") { setMode("view"); setEdit(undefined); setOff(false); }
                else { setMode("edit"); setViewing(null); }
              }}>
              {mode === "edit" ? <Check size={17} /> : <Pencil size={17} />}
            </button>
            {mode === "edit" && <>
              <button type="button" className="icon-button" aria-haspopup="dialog" aria-label={t("공강 설정")}
                data-tooltip={t("공강 설정")} onClick={() => { setSelectedDays(offDays); setOff(true); }}><Sun size={17} /></button>
              <button type="button" className="icon-button primary" aria-haspopup="dialog" aria-label={t("수업 추가")}
                data-tooltip={t("수업 추가")} onClick={() => setEdit(null)}><Plus size={18} /></button>
            </>}
            <button type="button" className="icon-button timetable-expand" aria-pressed={expanded}
              aria-label={t(expanded ? "시간표 복원" : "시간표 최대화")} data-tooltip={t(expanded ? "시간표 복원" : "시간표 최대화")}
              onClick={() => setExpanded(active => !active)}>
              {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
            </button>
          </div>
        </div>}
      </PageHeading>
      {densityDialog && <Modal title={t("시간표 시간 간격")} className="timetable-density-dialog" onClose={() => setDensityDialog(false)}>
        <div className="timetable-density-options">
          {([[0, "화면에 맞춤"], [64, "보통"], [80, "넓게"], [104, "아주 넓게"]] as const).map(([unit, label]) =>
            <button key={unit} type="button" aria-pressed={density === unit} onClick={() => { setDensity(unit); setDensityDialog(false); }}>
              {t(label)}{density === unit && <Check size={16} aria-hidden="true" />}
            </button>)}
        </div>
      </Modal>}
      {!data.timetableConfigured ? (
        <section className="glass empty">
          <p>{t("홈에서 메인 학기를 설정하세요.")}</p>
          <button type="button" onClick={onOpenHome}>{t("홈으로")}</button>
        </section>
      ) : (
        <div className="timetable-layout"
          data-timetable-theme={appearance.mode === "manual" ? undefined : theme.dark ? "dark" : "light"}
          style={appearance.mode === "manual" ? undefined : {
            "--timetable-surface": theme.surface, "--timetable-accent": theme.accent,
          } as CSSProperties}>
          <section
            ref={panel}
            className="timetable-panel"
            onScroll={event => {
              const saved = viewState.current;
              if (saved?.semester === term.name) {
                saved.scrollLeft = event.currentTarget.scrollLeft;
                saved.scrollTop = event.currentTarget.scrollTop;
              }
            }}
            style={{ "--hour-unit": `${unit}px`, "--week-days": days } as React.CSSProperties}
          >
            <div className="timetable-content">
            <div className="week-grid">
            <div className="week-headers">
              <span />
              {weekdays.slice(0, days).map((day, i) => (
                <div
                  key={day}
                  className={offDays.includes(i) ? "off-header" : ""}
                >
                  {t(day)}
                  {offDays.includes(i) && <small className="timetable-off-tag">{t("공강")}</small>}
                </div>
              ))}
            </div>
            <div className="week-body" style={{ height: gridHeight }}>
              <div className="time-axis">
                {Array.from({ length: (end - start) / 60 }, (_, i) => (
                  <span key={i} style={{ top: i * unit }}>
                    {String(start / 60 + i).padStart(2, "0")}:00
                  </span>
                ))}
              </div>
              {weekdays.slice(0, days).map((day, i) => (
                <div
                  key={day}
                  className={`week-column ${offDays.includes(i) ? "off-column" : ""}`}
                  onDoubleClick={(event) => {
                    if (
                      mode === "edit" &&
                      event.target === event.currentTarget &&
                      !offDays.includes(i)
                    )
                      setEdit(null);
                  }}
                >
                  {!offDays.includes(i) && (
                    scheduled
                      .filter((s) => s.day === i)
                      .map((s) => {
                        const size =
                          ((minute(s.end_time) - minute(s.start_time)) / 60) *
                          unit;
                        return (
                          <button
                            key={s.id}
                            className={`session-card ${size < 90 ? "compact" : ""} ${size < 68 ? "short" : ""} ${size < 44 ? "tiny" : ""}`}
                            title={`${name(s)} / ${s.start_time}–${s.end_time} / ${[s.professor, s.room].filter(Boolean).join(" / ")}`}
                            style={{
                              top: ((minute(s.start_time) - start) / 60) * unit,
                              height: Math.max(minimumCardHeight, size - 4),
                              left: `calc(${(lanes.get(s.id)?.lane || 0) * 100 / (lanes.get(s.id)?.count || 1)}% + 3px)`,
                              right: "auto",
                              width: `calc(${100 / (lanes.get(s.id)?.count || 1)}% - 6px)`,
                              "--course-color": sessionColor(s),
                            } as CSSProperties}
                            onClick={() => choose(s)}
                          >
                            <strong>{name(s)}</strong>
                            <small>
                              {s.start_time} – {s.end_time}
                            </small>
                            {(s.professor || s.room) && (
                              <small className="session-detail">
                                {[s.professor, s.room]
                                  .filter(Boolean)
                                  .join(" / ")}
                              </small>
                            )}
                            {work(s)}
                          </button>
                        );
                      })
                  )}
                </div>
              ))}
            </div>
            </div>
          {online.length > 0 && (
            <section className="online-courses" aria-label={t("비대면 수업")}>
              <header>
                <span>
                  <Monitor size={17} />
                  <strong>{t("비대면 수업")}</strong>
                </span>
                <small>{online.length}{t("개")}</small>
              </header>
              <div className="online-course-list">
                {online.map((s) => (
                  <button
                    key={s.id}
                    className="online-course"
                    style={
                      {
                        "--course-color": sessionColor(s),
                      } as React.CSSProperties
                    }
                    onClick={() => choose(s)}
                    title={`${name(s)} ${mode === "edit" ? t("수정") : t("일정 보기")}`}
                  >
                    <span className="online-course-title">
                      <strong>{name(s)}</strong>
                      <ArrowUpRight size={15} />
                    </span>
                    {s.professor && (
                      <small title={s.professor}>{s.professor}</small>
                    )}
                    {work(s)}
                  </button>
                ))}
              </div>
            </section>
          )}
            </div>
          </section>
        </div>
      )}
      {viewing && (
        <SessionViewer
          session={viewing}
          name={name(viewing)}
          onClose={() => setViewing(null)}
        />
      )}
      {colorDialog && <TimetableColorDialog appearance={appearance} palette={palette}
        courses={courseList.map(session => ({ session, title: name(session) }))}
        presets={colors.presets} pending={colorPending}
        onSave={(style, preset) => void saveAppearance(style, preset).catch(() => {})} onClose={() => setColorDialog(false)} />}
      {edit !== undefined && (
        <SessionEditor
          key={edit?.id ?? "new"}
          session={edit}
          semester={term.name}
          onClose={() => setEdit(undefined)}
          onDelete={() => edit && setDeleteId(edit.id)}
        />
      )}
      {off && (
        <Modal title={t("공강 설정")} onClose={() => setOff(false)}>
          <div className="off-choices">
            {weekdays.map((day, i) => (
              <button
                key={day}
                className={selectedDays.includes(i) ? "selected" : ""}
                onClick={() =>
                  setSelectedDays((value) =>
                    value.includes(i)
                      ? value.filter((d) => d !== i)
                      : [...value, i],
                  )
                }
              >
                {t(day)}
                <Sun size={16} />
              </button>
            ))}
          </div>
          <div className="dialog-actions">
            <span />
            <button
              className="primary"
              onClick={() =>
                void mutate("timetable.off", {
                  days: selectedDays,
                  semester: term.name,
                })
                  .then(() => setOff(false))
                  .catch(() => {})
              }
            >{t("저장")}{" "}</button>
          </div>
        </Modal>
      )}
      {deleteId !== null && (
        <Modal title={t("정말 삭제하시겠습니까?")} onClose={() => setDeleteId(null)}>
          <div className="dialog-actions">
            <span />
            <button onClick={() => setDeleteId(null)}>{t("취소")}</button>
            <button
              className="danger"
              onClick={() =>
                void mutate("timetable.delete", { id: deleteId })
                  .then(() => {
                    setDeleteId(null);
                    setEdit(undefined);
                  })
                  .catch(() => {})
              }
            >{t("삭제")}{" "}</button>
          </div>
        </Modal>
      )}
    </section>
  );
}

function SessionViewer({
  session,
  name,
  onClose,
}: {
  session: Session;
  name: string;
  onClose: () => void;
}) {
  useLanguage();
  const { data, openEvent } = useCalix();
  const [filter, setFilter] = useState<"pending" | "all" | "done">("pending");
  const courseEvents = data.events.filter(
    (e) =>
      e.course_id === session.course_id &&
      session.course_id > 0 &&
      (e.kind === "assignment" || e.kind === "movie"),
  );
  const events = courseEvents.filter(
    (e) => filter === "all" || e.completed === (filter === "done"),
  );
  const schedule = session.is_online
    ? t("정해진 시간 없음")
    : t("{0}요일 {1}–{2}", [t(weekdays[session.day]), session.start_time, session.end_time]);
  return (
    <Modal title={name} onClose={onClose} wide={courseEvents.length > 0} className="session-viewer">
      <dl className="session-facts">
        <div><dt>{t("교수명")}</dt><dd>{session.professor?.trim() || t("미등록")}</dd></div>
        <div><dt>{t("시간")}</dt><dd>{schedule}</dd></div>
        <div><dt>{t("강의실")}</dt><dd>{session.room?.trim() || (session.is_online ? t("온라인") : t("미등록"))}</dd></div>
      </dl>
      {courseEvents.length > 0 && <div className="segmented session-event-filters" aria-label={t("수업 일정 상태")}>
        {(
          [
            ["pending", "미완료"],
            ["all", "전체"],
            ["done", "완료"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            aria-pressed={filter === id}
            className={filter === id ? "selected" : ""}
            onClick={() => setFilter(id)}
          >
            {t(label)}
          </button>
        ))}
      </div>}
      {events.length ? <div className="session-event-lists">
        {(["assignment", "movie"] as const).map((kind) => {
          const rows = events.filter((e) => e.kind === kind);
          return (
            <section key={kind}>
              <h3>
                {kind === "assignment" ? t("과제") : t("영상")}{" "}
                <span className="count-pill">{rows.length}</span>
              </h3>
              {rows.map((e) => (
                <button
                  className={`session-event-row ${e.completed ? "completed" : ""}`}
                  key={e.key}
                  onClick={() => {
                    onClose();
                    openEvent(e.key);
                  }}
                >
                  <TypeBadge event={e} />
                  <span className="session-event-content">
                    <strong>{e.title}</strong>
                    <span className="session-event-metadata">
                      <small>{dueText(e.due_at)}</small>
                      <small
                        className={
                          !e.completed &&
                          e.due_at &&
                          new Date(e.due_at).getTime() < Date.now()
                            ? "danger"
                            : "muted"
                        }
                      >
                        {status(e)}
                      </small>
                    </span>
                  </span>
                </button>
              ))}
            </section>
          );
        })}
      </div> : <p className="session-events-empty" role="status">
        {session.course_id <= 0 ? t("연결된 강의 없음") : courseEvents.length === 0 ? t("과제, 영상 없음") : filter === "pending" ? t("미완료 일정 없음") : t("완료 일정 없음")}
      </p>}
    </Modal>
  );
}

function SessionEditor({
  session,
  semester,
  onClose,
  onDelete,
}: {
  session: Session | null;
  semester: string;
  onClose: () => void;
  onDelete: () => void;
}) {
  useLanguage();
  const { data, mutate } = useCalix();
  const [form, setForm] = useState({
    course_id: session?.course_id || 0,
    title:
      session?.title ||
      data.courses.find((c) => c.id === session?.course_id)?.name ||
      "",
    is_online: !!session?.is_online,
    day: session?.day || 0,
    start_time: session?.start_time || "09:00",
    end_time: session?.end_time || "10:30",
    professor: session?.professor || "",
    room: session?.room || "",
    color: session?.color || "#af527f",
  });
  const [extra, setExtra] = useState<
    { key: number; day: number; start_time: string; end_time: string; room: string }[]
  >([]);
  const nextSlot = useRef(0);
  const [saving, setSaving] = useState(false);
  const field = (
    key: "title" | "professor" | "room" | "color" | "start_time" | "end_time",
    value: string,
  ) => setForm((previous) => ({ ...previous, [key]: value }));
  return (
    <Modal title={session ? t("수업 수정") : t("수업 추가")} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (saving) return;
          setSaving(true);
          void mutate("timetable.save", {
            ...form,
            semester,
            id: session?.id,
            ...(!form.is_online
              ? {
                  slots: [
                    {
                      day: form.day,
                      start_time: form.start_time,
                      end_time: form.end_time,
                      room: form.room,
                    },
                    ...extra.map(({ day, start_time, end_time, room }) => ({
                      day, start_time, end_time, room,
                    })),
                  ],
                }
              : {}),
          })
            .then(onClose)
            .catch(() => {})
            .finally(() => setSaving(false));
        }}
      >
        <label>{t("연결 수업")}{" "}<select
            aria-label={t("연결 수업")}
            value={form.course_id}
            onChange={(event) => {
              const id = Number(event.target.value);
              setForm((previous) => ({
                ...previous,
                course_id: id,
                title: id
                  ? data.courses.find((c) => c.id === id)?.name ||
                    previous.title
                  : previous.title,
              }));
            }}
          >
            <option value={0}>{t("직접 입력")}</option>
            {data.courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>{t("수업명")}{" "}<input
            aria-label={t("수업명")}
            value={form.title}
            onChange={(event) => field("title", event.target.value)}
            maxLength={120}
            required
            placeholder={t("수업명")}
          />
        </label>
        <label className="online-toggle">
          <input
            type="checkbox"
            checked={form.is_online}
            onChange={(event) =>
              setForm((previous) => ({
                ...previous,
                is_online: event.target.checked,
              }))
            }
          />
          <span>
            <strong>{t("비대면 수업")}</strong>
            <small>{t("시간표 하단에 표시")}</small>
          </span>
          <Monitor size={19} />
        </label>
        {!form.is_online && (
          <>
            <div className="form-grid">
              <label>{t("요일")}{" "}<select
                  aria-label={t("요일")}
                  value={form.day}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      day: Number(event.target.value),
                    }))
                  }
                >
                  {weekdays.map((day, i) => (
                    <option key={day} value={i}>
                      {t(day)}{t("요일")}{" "}</option>
                  ))}
                </select>
              </label>
              <label>{t("강의실")}{" "}<input
                  aria-label={t("강의실")}
                  value={form.room}
                  maxLength={100}
                  onChange={(event) => field("room", event.target.value)}
                />
              </label>
            </div>
            <div className="form-grid">
              <TimeField label={t("시작")} value={form.start_time} onChange={(value) => field("start_time", value)} />
              <TimeField label={t("종료")} value={form.end_time} onChange={(value) => field("end_time", value)} />
            </div>
          </>
        )}
        {!form.is_online && (
          <div className="additional-slots">
            {extra.map((slot, index) => (
              <fieldset key={slot.key} className="slot-editor">
                <legend>{t("시간")}{" "}{index + 2}</legend>
                <div className="form-grid">
                  <label>{t("요일")}{" "}<select
                      aria-label={t("시간 {0} 요일", [String(index + 2)])}
                      value={slot.day}
                      onChange={(e) =>
                        setExtra((rows) =>
                          rows.map((r, i) =>
                            i === index
                              ? { ...r, day: Number(e.target.value) }
                              : r,
                          ),
                        )
                      }
                    >
                      {weekdays.map((day, i) => (
                        <option key={day} value={i}>
                          {t(day)}{t("요일")}{" "}</option>
                      ))}
                    </select>
                  </label>
                  <label>{t("강의실")}{" "}<input
                      aria-label={t("시간 {0} 강의실", [String(index + 2)])}
                      value={slot.room}
                      maxLength={100}
                      onChange={(e) =>
                        setExtra((rows) =>
                          rows.map((r, i) =>
                            i === index ? { ...r, room: e.target.value } : r,
                          ),
                        )
                      }
                    />
                  </label>
                </div>
                <div className="form-grid">
                  {(["start_time", "end_time"] as const).map((key, i) => (
                    <TimeField key={key}
                      caption={i ? t("종료") : t("시작")}
                      label={t("시간 {0} {1}", [String(index + 2), String(i ? "종료" : "시작")])}
                      value={slot[key]}
                      onChange={(value) => setExtra((rows) =>
                        rows.map((row) => row.key === slot.key ? { ...row, [key]: value } : row),
                      )}
                    />
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setExtra((rows) => rows.filter((_, i) => i !== index))
                  }
                >{t("시간 삭제")}{" "}</button>
              </fieldset>
            ))}
            <button
              type="button"
              disabled={extra.length >= 13}
              onClick={() => {
                const key = nextSlot.current++;
                setExtra((rows) => [
                  ...rows,
                  {
                    key,
                    day:
                      (rows.at(-1)?.day ?? form.day) + 1 > 6
                        ? 0
                        : (rows.at(-1)?.day ?? form.day) + 1,
                    start_time: form.start_time,
                    end_time: form.end_time,
                    room: form.room,
                  },
                ]);
              }}
            >
              <Plus size={16} />{t("시간 추가")}{" "}</button>
          </div>
        )}
        <div className="form-grid">
          <label>{t("담당 교수")}{" "}<input
              aria-label={t("담당 교수")}
              value={form.professor}
              maxLength={120}
              onChange={(event) => field("professor", event.target.value)}
            />
          </label>
          <ColorField caption label={t("색상")} value={form.color} onChange={value => field("color", value)} />
        </div>
        <div className="dialog-actions">
          {session && (
            <button type="button" className="danger" onClick={onDelete}>
              <Trash2 size={16} />{t("삭제")}{" "}</button>
          )}
          <span />
          <button className="primary" disabled={saving}>
            {saving ? t("저장 중") : t("저장")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
