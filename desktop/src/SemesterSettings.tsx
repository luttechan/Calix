import { semesterName, t, useLanguage } from "./i18n";
import { useState } from "react";
import { CalendarRange, ChevronDown, Plus, TriangleAlert } from "lucide-react";
import { Modal, useCalix } from "./App";
import { NumberField } from "./NumberField";
import { rpc } from "./bridge";
import type { Snapshot } from "./types";
import "./semester-settings.css";

type Term = Snapshot["timetableTerms"][number];
type Rosters = Record<string, number[]>;

export function MainSemesterControl() {
  useLanguage();
  const { data, mutate } = useCalix();
  const [dialog, setDialog] = useState<"change" | "add" | "setup" | null>(null);
  const [next, setNext] = useState("");
  const [saving, setSaving] = useState(false);

  return <>
    <button className="home-semester-button" type="button" aria-haspopup="dialog" onClick={() => {
      setNext(data.mainTerm);
      setDialog(data.timetableConfigured ? "change" : "setup");
    }}>
      <CalendarRange size={19} aria-hidden="true" />
      <span><small>{t("메인 학기")}</small><strong>{data.timetableConfigured ? data.mainTerm : t("학기 설정")}</strong></span>
      <ChevronDown size={15} aria-hidden="true" />
    </button>
    {dialog === "change" && (
      <Modal title={t("메인 학기를 변경하시겠습니까?")} onClose={() => { if (!saving) setDialog(null); }}>
        <form onSubmit={(event) => {
          event.preventDefault();
          if (saving || next === data.mainTerm) return;
          setSaving(true);
          void mutate("semester.main", { name: next })
            .then(() => setDialog(null)).catch(() => {}).finally(() => setSaving(false));
        }}>
          <p className="semester-warning"><TriangleAlert size={18} aria-hidden="true" />
            <span>{t("변경 후 시작하는 동기화에서 새 Canvas 과목은 선택한 학기에 추가됩니다.")}</span>
          </p>
          <div className="form-grid semester-switch-fields">
            <div><small>{t("현재 학기")}</small><strong>{data.mainTerm}</strong></div>
            <label>{t("변경할 학기")}{" "}<select value={next} disabled={saving} onChange={(event) => setNext(event.target.value)}>
                {data.timetableTerms.map((term) => <option key={term.name} value={term.name}>{semesterName(term.name)}</option>)}
              </select>
            </label>
          </div>
          <div className="dialog-actions">
            <button type="button" disabled={saving} onClick={() => setDialog("add")}>{t("학기 추가")}</button>
            <span />
            <button type="button" disabled={saving} onClick={() => setDialog(null)}>{t("취소")}</button>
            <button className="primary" disabled={saving || next === data.mainTerm}>{t("변경")}</button>
          </div>
        </form>
      </Modal>
    )}
    {(dialog === "setup" || dialog === "add") && (
      <TermEditor setup={dialog === "setup"} onClose={() => setDialog(dialog === "add" ? "change" : null)}
        onSaved={(name) => {
          if (dialog === "add") setNext(name);
          setDialog(dialog === "add" ? "change" : null);
        }} />
    )}
  </>;
}

export function SemesterSettings() {
  useLanguage();
  const { data, notify } = useCalix();
  const [add, setAdd] = useState(false);
  const [rosters, setRosters] = useState<Rosters | null>(null);
  const [loading, setLoading] = useState(false);
  const { timetableTerms: terms, mainTerm } = data;
  const openMove = async () => {
    setLoading(true);
    try {
      setRosters(await rpc<Rosters>("semester.roster"));
    } catch (error) {
      notify((error as Error).message, true);
    } finally {
      setLoading(false);
    }
  };
  return <>
    <section className="glass settings-panel semester-settings">
      <div className="settings-heading"><CalendarRange aria-hidden="true" /><h2>{t("학기")}</h2></div>
      {data.timetableConfigured ? <>
        <div className="semester-settings-controls">
          <button type="button" onClick={() => setAdd(true)}><Plus size={16} aria-hidden="true" />{t("학기 추가")}</button>
          <button type="button" disabled={loading || terms.length < 2 || !data.courses.length}
            onClick={() => void openMove()}>{t("Canvas 과목 옮기기")}</button>
        </div>
        <ul className="semester-list">
          {terms.map((term) => <li key={term.name}>
            <strong>{semesterName(term.name)}</strong>
            {term.name === mainTerm && <span className="count-pill">{t("메인 학기")}</span>}
          </li>)}
        </ul>
      </> : <p className="muted">{t("홈에서 메인 학기를 설정하세요.")}</p>}
    </section>
    {add && <TermEditor setup={false} onClose={() => setAdd(false)} onSaved={() => setAdd(false)} />}
    {rosters && <CourseTransfer terms={terms} rosters={rosters} onClose={() => setRosters(null)} />}
  </>;
}

function TermEditor({ setup, onClose, onSaved }: {
  setup: boolean;
  onClose: () => void;
  onSaved: (name: string) => void;
}) {
  useLanguage();
  const { mutate } = useCalix();
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [term, setTerm] = useState(today.getMonth() < 7 ? "1" : "2");
  const [saving, setSaving] = useState(false);
  return (
    <Modal title={setup ? t("메인 학기 설정") : t("학기 추가")} onClose={() => { if (!saving) onClose(); }}>
      <form onSubmit={(event) => {
        event.preventDefault();
        if (saving) return;
        setSaving(true);
        void mutate(setup ? "semester.configure" : "semester.add", {
          year, term: term === "1" || term === "2" ? Number(term) : term,
        }).then((name) => onSaved(String(name))).catch(() => {}).finally(() => setSaving(false));
      }}>
        {setup && <p className="semester-warning"><TriangleAlert size={18} aria-hidden="true" />
          <span>{t("기존 시간표와 학점을 선택한 학기에 연결합니다.")}</span>
        </p>}
        <div className="form-grid">
          <label>{t("학년도")}<NumberField aria-label={t("학년도")} min={1900} max={2200}
            step={1} required value={year} onValueChange={setYear} /></label>
          <label>{t("학기")}<select value={term} onChange={(event) => setTerm(event.target.value)}>
            <option value="1">{t("1학기")}</option><option value="2">{t("2학기")}</option>
            <option value="여름">{t("여름 계절학기")}</option><option value="겨울">{t("겨울 계절학기")}</option>
          </select></label>
        </div>
        <div className="dialog-actions">
          <span />
          <button type="button" disabled={saving} onClick={onClose}>{t("취소")}</button>
          <button className="primary" disabled={saving}>{setup ? t("설정") : t("추가")}</button>
        </div>
      </form>
    </Modal>
  );
}

function CourseTransfer({ terms, rosters, onClose }: { terms: Term[]; rosters: Rosters; onClose: () => void }) {
  useLanguage();
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
  return <Modal title={t("Canvas 과목 옮기기")} onClose={() => { if (!saving) onClose(); }}>
    <form onSubmit={(event) => {
      event.preventDefault();
      if (saving || !selected.size || source === target) return;
      setSaving(true);
      void mutate("semester.move", { source, target, course_ids: [...selected] })
        .then((count) => { notify(`과목 ${count}개를 옮겼습니다.`); onClose(); })
        .catch(() => {}).finally(() => setSaving(false));
    }}>
      <div className="form-grid">
        <label>{t("출발 학기")}<select value={source} disabled={saving} onChange={(event) => {
          setSource(event.target.value);
          setSelected(new Set());
        }}>{terms.map((term) => <option key={term.name} value={term.name}>{semesterName(term.name)}</option>)}</select></label>
        <label>{t("이동할 학기")}<select value={target} disabled={saving} onChange={(event) => setTarget(event.target.value)}>
          {terms.map((term) => <option key={term.name} value={term.name}>{semesterName(term.name)}</option>)}
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
      </div> : <p className="muted">{t("등록된 Canvas 과목 없음")}</p>}
      <div className="dialog-actions">
        <span />
        <button type="button" disabled={saving} onClick={onClose}>{t("취소")}</button>
        <button className="primary" disabled={saving || !selected.size || source === target}>{t("과목 옮기기")}</button>
      </div>
    </form>
  </Modal>;
}
