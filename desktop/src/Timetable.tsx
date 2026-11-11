import { NumberField } from "./NumberField";
import { useMemo, useState } from "react";
import { Plus, Sun, Trash2, Monitor, ArrowUpRight } from "lucide-react";
import { Modal, TypeBadge, useCalix } from "./App";
import { weekdays, dueText, status } from "./dates";
import { useTimetableScale } from "./useTimetableScale";
import type { Session } from "./types";

const minute = (value: string) => {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
};
export function TimetablePage() {
  const { data, mutate } = useCalix();
  const [days, setDays] = useState(5);
  const [mode, setMode] = useState<"view" | "edit">("view");
  const [semester, setSemester] = useState(data.mainTerm);
  const [termDialog, setTermDialog] = useState(!data.timetableConfigured);
  const [viewing, setViewing] = useState<Session | null>(null);
  const term =
    data.timetableTerms.find((t) => t.name === semester) ||
    data.timetableTerms.find((t) => t.name === data.mainTerm)!;
  const offDays = term.offDays;
  const sessions = data.sessions.filter((s) => s.semester === term.name);
  const choose = (s: Session) => (mode === "edit" ? setEdit(s) : setViewing(s));
  const [edit, setEdit] = useState<Session | null | undefined>();
  const [off, setOff] = useState(false);
  const [selectedDays, setSelectedDays] = useState(offDays);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const scheduled = sessions.filter((s) => !s.is_online);
  const online = sessions.filter((s) => s.is_online);
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
    online.length ? 95 : 0,
    data.timetableConfigured,
  );
  const workloads = useMemo(() => {
    const counts = new Map<number, { assignment: number; movie: number }>();
    const now = Date.now();
    for (const event of data.events) {
      if (
        event.completed ||
        (event.due_at && new Date(event.due_at).getTime() <= now)
      )
        continue;
      if (event.kind !== "assignment" && event.kind !== "movie") continue;
      const row = counts.get(event.course_id) || { assignment: 0, movie: 0 };
      row[event.kind]++;
      counts.set(event.course_id, row);
    }
    return counts;
  }, [data.events]);
  const name = (s: Session) =>
    s.title || data.courses.find((c) => c.id === s.course_id)?.name || "수업";
  const work = (s: Session) => {
    const count = workloads.get(s.course_id) || { assignment: 0, movie: 0 };
    return (
      s.course_id > 0 && (
        <div className="session-work">
          <span>과제 {count.assignment}</span>
          <span>영상 {count.movie}</span>
        </div>
      )
    );
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">이번 주</p>
          <h1>시간표</h1>
        </div>
        <div className="toolbar">
          <div className="segmented" aria-label="시간표 모드">
            <button
              aria-pressed={mode === "view"}
              className={mode === "view" ? "selected" : ""}
              onClick={() => {
                setMode("view");
                setEdit(undefined);
                setOff(false);
              }}
            >
              열람 모드
            </button>
            <button
              aria-pressed={mode === "edit"}
              className={mode === "edit" ? "selected" : ""}
              onClick={() => {
                setMode("edit");
                setViewing(null);
              }}
            >
              편집 모드
            </button>
          </div>
          <div className="segmented">
            {[5, 7].map((n) => (
              <button
                key={n}
                className={days === n ? "selected" : ""}
                onClick={() => setDays(n)}
              >
                {n === 5 ? "주중" : "주간"}
              </button>
            ))}
          </div>
          {mode === "edit" && data.timetableConfigured && (
            <>
              <button
                onClick={() => {
                  setSelectedDays(offDays);
                  setOff(true);
                }}
              >
                공강 설정
              </button>
              <button className="primary" onClick={() => setEdit(null)}>
                <Plus size={17} />
                수업 추가
              </button>
            </>
          )}
        </div>
      </div>
      <div className="semester-toolbar">
        <select
          aria-label="시간표 학기"
          value={term.name}
          onChange={(event) => {
            setSemester(event.target.value);
            setViewing(null);
            setEdit(undefined);
            setOff(false);
          }}
        >
          {data.timetableTerms.map((t) => (
            <option key={t.name} value={t.name}>
              {t.name}
              {t.name === data.mainTerm ? " (메인)" : ""}
            </option>
          ))}
        </select>
        <button onClick={() => setTermDialog(true)}>학기 추가</button>
        {data.timetableConfigured &&
          (term.name === data.mainTerm ? (
            <span className="count-pill">메인 학기</span>
          ) : (
            <button
              onClick={() =>
                void mutate("timetable.term.main", { name: term.name }).catch(
                  () => {},
                )
              }
            >
              메인 학기로 설정
            </button>
          ))}
      </div>
      {!data.timetableConfigured ? (
        <section className="glass empty">
          <p>학기를 설정하세요.</p>
          <button className="primary" onClick={() => setTermDialog(true)}>
            학기 설정
          </button>
        </section>
      ) : (
        <>
          <section
            ref={panel}
            className={`glass timetable-panel ${online.length ? "with-online" : ""}`}
            style={{ "--hour-unit": `${unit}px` } as React.CSSProperties}
          >
            <div
              className="week-headers"
              style={{
                gridTemplateColumns: `48px repeat(${days},minmax(105px,1fr))`,
              }}
            >
              <span />
              {weekdays.slice(0, days).map((day, i) => (
                <div
                  key={day}
                  className={offDays.includes(i) ? "off-header" : ""}
                >
                  {day}
                  <small>{offDays.includes(i) ? "공강" : ""}</small>
                </div>
              ))}
            </div>
            <div
              className="week-body"
              style={{
                gridTemplateColumns: `48px repeat(${days},minmax(105px,1fr))`,
                height,
              }}
            >
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
                  {offDays.includes(i) ? (
                    <div className="off-marker">
                      <span>
                        <Sun size={30} />
                      </span>
                      <strong>공강</strong>
                    </div>
                  ) : (
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
                              height: Math.max(20, size - 4),
                              borderLeftColor: s.color || "var(--accent)",
                              background: `color-mix(in srgb,${s.color || "var(--accent)"} 12%,var(--surface))`,
                            }}
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
          </section>
          {online.length > 0 && (
            <section className="glass online-courses" aria-label="비대면 수업">
              <header>
                <span>
                  <Monitor size={17} />
                  <strong>비대면 수업</strong>
                </span>
                <small>{online.length}개</small>
              </header>
              <div className="online-course-list">
                {online.map((s) => (
                  <button
                    key={s.id}
                    className="online-course"
                    style={
                      {
                        "--course-color": s.color || "var(--accent)",
                      } as React.CSSProperties
                    }
                    onClick={() => choose(s)}
                    title={`${name(s)} ${mode === "edit" ? "수정" : "일정 보기"}`}
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
        </>
      )}
      {termDialog && (
        <TermEditor
          setup={!data.timetableConfigured}
          onClose={() => setTermDialog(false)}
          onSaved={(name) => {
            setSemester(name);
            setTermDialog(false);
          }}
        />
      )}
      {viewing && (
        <SessionViewer
          session={viewing}
          name={name(viewing)}
          onClose={() => setViewing(null)}
        />
      )}
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
        <Modal title="공강 설정" onClose={() => setOff(false)}>
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
                {day}
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
            >
              저장
            </button>
          </div>
        </Modal>
      )}
      {deleteId !== null && (
        <Modal title="정말 삭제하시겠습니까?" onClose={() => setDeleteId(null)}>
          <div className="dialog-actions">
            <span />
            <button onClick={() => setDeleteId(null)}>취소</button>
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
            >
              삭제
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function TermEditor({
  setup,
  onClose,
  onSaved,
}: {
  setup: boolean;
  onClose: () => void;
  onSaved: (name: string) => void;
}) {
  const { mutate } = useCalix();
  const [year, setYear] = useState(new Date().getFullYear());
  const [term, setTerm] = useState<number | string>(
    new Date().getMonth() < 7 ? 1 : 2,
  );
  const [saving, setSaving] = useState(false);
  return (
    <Modal title={setup ? "학기 설정" : "학기 추가"} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (saving) return;
          setSaving(true);
          void mutate(
            setup ? "timetable.term.configure" : "timetable.term.add",
            { year, term },
          )
            .then(() =>
              onSaved(
                `${year}학년도 ${term}${typeof term === "number" ? "학기" : " 계절학기"}`,
              ),
            )
            .catch(() => {})
            .finally(() => setSaving(false));
        }}
      >
        {setup && (
          <p className="muted">기존 시간표를 선택한 학기로 연결합니다.</p>
        )}
        <div className="form-grid">
          <label>
            학년도
            <NumberField
              aria-label="학년도"

              min={1900}
              max={2200}
              step={1}
              required
              value={year}
              onValueChange={setYear}
            />
          </label>
          <label>
            학기
            <select
              aria-label="학기"
              value={term}
              onChange={(e) =>
                setTerm(
                  ["1", "2"].includes(e.target.value)
                    ? Number(e.target.value)
                    : e.target.value,
                )
              }
            >
              <option value={1}>1학기</option>
              <option value={2}>2학기</option>
              <option value="여름">여름 계절학기</option>
              <option value="겨울">겨울 계절학기</option>
            </select>
          </label>
        </div>
        <div className="dialog-actions">
          <span />
          <button type="button" onClick={onClose}>
            취소
          </button>
          <button className="primary" disabled={saving}>
            {saving ? "저장 중" : setup ? "설정" : "추가"}
          </button>
        </div>
      </form>
    </Modal>
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
  const { data, openEvent } = useCalix();
  const [filter, setFilter] = useState<"pending" | "all" | "done">("pending");
  const events = data.events.filter(
    (e) =>
      e.course_id === session.course_id &&
      session.course_id > 0 &&
      (filter === "all" || e.completed === (filter === "done")),
  );
  return (
    <Modal title={name} onClose={onClose} wide>
      <p className="muted">
        {[
          session.professor,
          session.is_online
            ? "비대면"
            : `${weekdays[session.day]} ${session.start_time}–${session.end_time}`,
          session.room,
        ]
          .filter(Boolean)
          .join(" / ")}
      </p>
      <div className="segmented" aria-label="수업 일정 상태">
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
            {label}
          </button>
        ))}
      </div>
      <div className="session-event-lists">
        {(["assignment", "movie"] as const).map((kind) => {
          const rows = events.filter((e) => e.kind === kind);
          return (
            <section key={kind}>
              <h3>
                {kind === "assignment" ? "과제" : "영상"}{" "}
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
                  <span>
                    <strong>{e.title}</strong>
                    <small>{dueText(e.due_at)}</small>
                  </span>
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
                </button>
              ))}
              {!rows.length && (
                <div className="empty">
                  {session.course_id > 0
                    ? "일정이 없습니다."
                    : "연결된 강의가 없습니다."}
                </div>
              )}
            </section>
          );
        })}
      </div>
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
    { day: number; start_time: string; end_time: string; room: string }[]
  >([]);
  const [saving, setSaving] = useState(false);
  const field = (
    key: "title" | "professor" | "room" | "color" | "start_time" | "end_time",
    value: string,
  ) => setForm((previous) => ({ ...previous, [key]: value }));
  return (
    <Modal title={session ? "수업 수정" : "수업 추가"} onClose={onClose}>
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
                    ...extra,
                  ],
                }
              : {}),
          })
            .then(onClose)
            .catch(() => {})
            .finally(() => setSaving(false));
        }}
      >
        <label>
          연결 수업
          <select
            aria-label="연결 수업"
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
            <option value={0}>직접 입력</option>
            {data.courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          수업명
          <input
            aria-label="수업명"
            value={form.title}
            onChange={(event) => field("title", event.target.value)}
            maxLength={120}
            required
            placeholder="수업명"
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
            <strong>비대면 수업</strong>
            <small>시간표 하단에 표시</small>
          </span>
          <Monitor size={19} />
        </label>
        {!form.is_online && (
          <>
            <div className="form-grid">
              <label>
                요일
                <select
                  aria-label="요일"
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
                      {day}요일
                    </option>
                  ))}
                </select>
              </label>
              <label>
                강의실
                <input
                  aria-label="강의실"
                  value={form.room}
                  maxLength={100}
                  onChange={(event) => field("room", event.target.value)}
                />
              </label>
            </div>
            <div className="form-grid">
              <label>
                시작
                <input
                  type="time"
                  aria-label="시작"
                  value={form.start_time}
                  onChange={(event) => field("start_time", event.target.value)}
                  required
                />
              </label>
              <label>
                종료
                <input
                  type="time"
                  aria-label="종료"
                  value={form.end_time}
                  onChange={(event) => field("end_time", event.target.value)}
                  required
                />
              </label>
            </div>
          </>
        )}
        {!form.is_online && (
          <div className="additional-slots">
            {extra.map((slot, index) => (
              <fieldset key={index} className="slot-editor">
                <legend>시간 {index + 2}</legend>
                <div className="form-grid">
                  <label>
                    요일
                    <select
                      aria-label={`시간 ${index + 2} 요일`}
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
                          {day}요일
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    강의실
                    <input
                      aria-label={`시간 ${index + 2} 강의실`}
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
                    <label key={key}>
                      {i ? "종료" : "시작"}
                      <input
                        required
                        type="time"
                        aria-label={`시간 ${index + 2} ${i ? "종료" : "시작"}`}
                        value={slot[key]}
                        onChange={(e) =>
                          setExtra((rows) =>
                            rows.map((r, n) =>
                              n === index ? { ...r, [key]: e.target.value } : r,
                            ),
                          )
                        }
                      />
                    </label>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setExtra((rows) => rows.filter((_, i) => i !== index))
                  }
                >
                  시간 삭제
                </button>
              </fieldset>
            ))}
            <button
              type="button"
              disabled={extra.length >= 13}
              onClick={() =>
                setExtra((rows) => [
                  ...rows,
                  {
                    day:
                      (rows.at(-1)?.day ?? form.day) + 1 > 6
                        ? 0
                        : (rows.at(-1)?.day ?? form.day) + 1,
                    start_time: form.start_time,
                    end_time: form.end_time,
                    room: form.room,
                  },
                ])
              }
            >
              <Plus size={16} />
              시간 추가
            </button>
          </div>
        )}
        <div className="form-grid">
          <label>
            담당 교수
            <input
              aria-label="담당 교수"
              value={form.professor}
              maxLength={120}
              onChange={(event) => field("professor", event.target.value)}
            />
          </label>
          <label>
            색상
            <input
              type="color"
              aria-label="색상"
              value={form.color}
              onChange={(event) => field("color", event.target.value)}
            />
          </label>
        </div>
        <div className="dialog-actions">
          {session && (
            <button type="button" className="danger" onClick={onDelete}>
              <Trash2 size={16} />
              삭제
            </button>
          )}
          <span />
          <button className="primary" disabled={saving}>
            {saving ? "저장 중" : "저장"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
