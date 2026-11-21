import { useState } from "react";
import { CalendarRange, Plus } from "lucide-react";
import { Modal, useCalix } from "./App";
import { DateField } from "./ChecklistDeadline";
import { TermEditor } from "./Timetable";
import { rpc } from "./bridge";
import type { Snapshot } from "./types";
import "./semester-settings.css";

type Term = Snapshot["timetableTerms"][number];
type Rosters = Record<string, number[]>;

export function SemesterSettings() {
  const { data, mutate, notify } = useCalix();
  const [editing, setEditing] = useState<Term | null>(null);
  const [add, setAdd] = useState(false);
  const [rosters, setRosters] = useState<Rosters | null>(null);
  const [busy, setBusy] = useState(false);
  const { timetableTerms: terms, mainTerm, semesterAutomatic, semesterSeasonal } = data;
  const apply = (method: string, params: Record<string, unknown> = {}) => {
    setBusy(true);
    void mutate(method, params).catch(() => {}).finally(() => setBusy(false));
  };
  const openMove = async () => {
    setBusy(true);
    try {
      setRosters(await rpc<Rosters>("semester.roster"));
    } catch (error) {
      // Keep read errors visible without refreshing the app state.
      notify((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const dated = terms.some((term) => term.startsOn);
  const ordered = [...terms].sort((a, b) =>
    (a.startsOn ?? "9999").localeCompare(b.startsOn ?? "9999") || b.name.localeCompare(a.name),
  );
  return <>
    <section className="glass settings-panel semester-settings">
      <div className="settings-heading">
        <CalendarRange aria-hidden="true" />
        <h2>학기</h2>
      </div>
      <div className="semester-settings-controls">
        {data.timetableConfigured && <label>
          메인 학기
          <select value={mainTerm} disabled={busy} onChange={(event) => apply("semester.main", { name: event.target.value })}>
            {ordered.map((term) => <option key={term.name}>{term.name}</option>)}
          </select>
        </label>}
        <button type="button" disabled={busy} onClick={() => setAdd(true)}>
          <Plus size={16} aria-hidden="true" />{data.timetableConfigured ? "학기 추가" : "학기 설정"}
        </button>
        <button type="button" className={dated ? "" : "primary"} disabled={busy}
          onClick={() => apply("semester.school")}>부산외대 학사일정 적용</button>
      </div>
      <label className="menu-option">
        <span><strong>날짜로 메인 학기 전환</strong><small>등록된 기간에 맞춰 실행 및 동기화 시 전환합니다.</small></span>
        <input type="checkbox" role="switch" aria-label="날짜로 메인 학기 전환"
          checked={!!semesterAutomatic} disabled={busy || !dated}
          onChange={(event) => apply("semester.mode", { automatic: event.target.checked })} />
      </label>
      {semesterAutomatic && <label className="menu-option">
        <strong>계절학기 포함</strong>
        <input type="checkbox" role="switch" checked={semesterSeasonal !== false} disabled={busy}
          onChange={(event) => apply("semester.mode", { seasonal: event.target.checked })} />
      </label>}
      {data.timetableConfigured && <>
        <div className="semester-period-heading">
          <h3>학기별 기간</h3>
          <button type="button" disabled={busy || terms.length < 2 || !data.courses.length}
            onClick={() => void openMove()}>Canvas 과목 옮기기</button>
        </div>
        <ul className="semester-periods">
          {ordered.map((term) => <li key={term.name}>
            <div>
              <strong>{term.name}</strong>
              {term.name === mainTerm && <span className="count-pill">메인</span>}
              <small>{term.startsOn && term.endsOn ? `${term.startsOn} ~ ${term.endsOn}` : "기간 미설정"}</small>
            </div>
            <button type="button" disabled={busy} aria-label={`${term.name} 날짜 편집`}
              onClick={() => setEditing(term)}>날짜 편집</button>
          </li>)}
        </ul>
      </>}
    </section>
    {add && <TermEditor setup={!data.timetableConfigured} inSettings
      onClose={() => setAdd(false)} onSaved={() => setAdd(false)} />}
    {editing && <PeriodEditor term={editing} onClose={() => setEditing(null)} />}
    {rosters && <CourseTransfer terms={ordered} rosters={rosters} onClose={() => setRosters(null)} />}
  </>;
}

function PeriodEditor({ term, onClose }: { term: Term; onClose: () => void }) {
  const { mutate } = useCalix();
  const [start, setStart] = useState(term.startsOn ?? "");
  const [end, setEnd] = useState(term.endsOn ?? "");
  const [saving, setSaving] = useState(false);
  return <Modal title={term.name} onClose={onClose}>
    <form onSubmit={(event) => {
      event.preventDefault();
      if (saving || !start || !end || start > end) return;
      setSaving(true);
      void mutate("semester.dates", { name: term.name, startsOn: start, endsOn: end })
        .then(onClose).catch(() => {}).finally(() => setSaving(false));
    }}>
      <div className="form-grid">
        <label>시작일<DateField label="학기 시작일" value={start} onChange={setStart} disabled={saving} /></label>
        <label>종료일<DateField label="학기 종료일" value={end} onChange={setEnd} disabled={saving} /></label>
      </div>
      <div className="dialog-actions">
        {term.startsOn && <button type="button" className="text-button" disabled={saving} onClick={() => {
          setSaving(true);
          void mutate("semester.dates", { name: term.name, startsOn: null, endsOn: null })
            .then(onClose).catch(() => {}).finally(() => setSaving(false));
        }}>기간 지우기</button>}
        <span />
        <button type="button" disabled={saving} onClick={onClose}>취소</button>
        <button className="primary" disabled={saving || !start || !end || start > end}>저장</button>
      </div>
    </form>
  </Modal>;
}

function CourseTransfer({ terms, rosters, onClose }: { terms: Term[]; rosters: Rosters; onClose: () => void }) {
  const { data, mutate, notify } = useCalix();
  const [source, setSource] = useState(
    [...terms].reverse().find((term) => term.name !== data.mainTerm && rosters[term.name]?.length)?.name ?? data.mainTerm,
  );
  const [target, setTarget] = useState(
    source === data.mainTerm ? [...terms].reverse().find((term) => term.name !== source)?.name ?? "" : data.mainTerm,
  );
  const [selected, setSelected] = useState(new Set<number>());
  const [saving, setSaving] = useState(false);
  const enrolled = new Set(rosters[source]);
  const courses = data.courses.filter((course) => enrolled.has(course.id));
  return <Modal title="Canvas 과목 옮기기" onClose={() => { if (!saving) onClose(); }}>
    <form onSubmit={(event) => {
      event.preventDefault();
      if (saving || !selected.size || source === target) return;
      setSaving(true);
      void mutate("semester.move", { source, target, course_ids: [...selected] })
        .then((count) => { notify(`과목 ${count}개를 옮겼습니다.`); onClose(); })
        .catch(() => {}).finally(() => setSaving(false));
    }}>
      <div className="form-grid">
        <label>출발 학기<select value={source} disabled={saving} onChange={(event) => {
          setSource(event.target.value);
          setSelected(new Set());
        }}>{terms.map((term) => <option key={term.name}>{term.name}</option>)}</select></label>
        <label>이동할 학기<select value={target} disabled={saving} onChange={(event) => setTarget(event.target.value)}>
          {terms.map((term) => <option key={term.name}>{term.name}</option>)}
        </select></label>
      </div>
      {courses.length ? <div className="grade-import-list">
        {courses.map((course) => <label key={course.id}>
          <input type="checkbox" checked={selected.has(course.id)} disabled={saving} onChange={(event) => {
            const next = new Set(selected);
            if (event.target.checked) next.add(course.id);
            else next.delete(course.id);
            setSelected(next);
          }} />
          <span>{course.name}</span>
        </label>)}
      </div> : <p className="muted">등록된 Canvas 과목 없음</p>}
      <div className="dialog-actions">
        <span />
        <button type="button" disabled={saving} onClick={onClose}>취소</button>
        <button className="primary" disabled={saving || !selected.size || source === target}>과목 옮기기</button>
      </div>
    </form>
  </Modal>;
}
