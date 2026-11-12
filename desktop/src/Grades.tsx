import { useEffect, useState } from "react";
import { Calculator, Link2, Plus, Save, Trash2 } from "lucide-react";
import { useCalix } from "./App";
import { rpc } from "./bridge";
import { NumberField } from "./NumberField";
import "./security-grades.css";

type Item = { id: string; title: string; credits: number; grade: string; category: string; excluded: number; linked: boolean };
type GradeData = {
  semester: string; scale: string; grades: string[]; items: Item[];
  summary: { gpa: string | null; graded_credits: number; earned_credits: number; registered_credits: number; pending: number };
};

function GradeRow({ item, grades, semester, refresh }: { item: Item; grades: string[]; semester: string; refresh: () => Promise<void> }) {
  const { mutate, notify } = useCalix();
  const [draft, setDraft] = useState(item);
  const [saving, setSaving] = useState(false);
  const [remove, setRemove] = useState(false);
  useEffect(() => {
    if (item.linked) setDraft(previous => ({ ...previous, title: item.title }));
  }, [item.linked, item.title]);
  const field = <K extends keyof Item>(key: K, value: Item[K]) => setDraft(previous => ({ ...previous, [key]: value }));
  return (
    <form className={"grade-row " + (draft.excluded ? "excluded" : "")} onSubmit={event => {
      event.preventDefault();
      if (saving) return;
      setSaving(true);
      void mutate("grades.save", { ...draft, excluded: !!draft.excluded, semester })
        .then(refresh).then(() => notify("저장됨")).catch(() => {}).finally(() => setSaving(false));
    }}>
      <label className="grade-course grade-field">
        <span className="grade-field-label">과목</span>
        <span className="grade-course-input">
        {item.linked && <Link2 size={14} aria-label="시간표 연결" />}
        <input aria-label="과목명" title={draft.title} value={draft.title} readOnly={item.linked} maxLength={200} required onChange={event => field("title", event.target.value)} />
        </span>
      </label>
      <label className="grade-field"><span className="grade-field-label">학점</span>
      <NumberField aria-label={item.title + " 학점"} value={draft.credits} min={0} max={30} step={0.5} required onValueChange={value => field("credits", value)} />
      </label>
      <label className="grade-field"><span className="grade-field-label">성적</span>
      <select aria-label={item.title + " 성적"} value={draft.grade} onChange={event => field("grade", event.target.value)}>
        <option value="">미입력</option>
        {draft.grade && !grades.includes(draft.grade) && <option value={draft.grade}>{draft.grade} (기준 변경 필요)</option>}
        {grades.map(grade => <option key={grade}>{grade}</option>)}
      </select>
      </label>
      <label className="grade-field"><span className="grade-field-label">분류</span>
      <select aria-label={item.title + " 분류"} value={draft.category} onChange={event => field("category", event.target.value)}>
        {["전공", "교양", "일반"].map(category => <option key={category}>{category}</option>)}
      </select>
      </label>
      <div className="grade-actions">
      <label className="grade-exclude"><input type="checkbox" checked={!!draft.excluded} onChange={event => field("excluded", Number(event.target.checked))} />제외</label>
      <button type="submit" className="icon-button" title="성적 저장" aria-label={item.title + " 저장"} disabled={saving}><Save size={17} /></button>
      {!item.linked && <button type="button" className="icon-button" title="과목 삭제" aria-label={item.title + " 삭제"} disabled={saving} onClick={() => setRemove(true)}><Trash2 size={16} /></button>}
      </div>
      {remove && <div className="grade-delete" role="alert">
        <span>정말 삭제하시겠습니까?</span>
        <button type="button" onClick={() => setRemove(false)}>취소</button>
        <button type="button" disabled={saving} onClick={() => {
          setSaving(true);
          void mutate("grades.delete", { id: item.id, semester }).then(refresh).catch(() => {}).finally(() => setSaving(false));
        }}>삭제</button>
      </div>}
    </form>
  );
}

export function GradesPage() {
  const { data, mutate, notify } = useCalix();
  const [semester, setSemester] = useState(data.mainTerm);
  const [grades, setGrades] = useState<GradeData | null>(null);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [pending, setPending] = useState(false);
  const refresh = async () => {
    const value = await rpc<GradeData>("grades.read", { semester });
    setGrades(value);
  };
  useEffect(() => {
    let active = true;
    setGrades(null);
    setError("");
    void rpc<GradeData>("grades.read", { semester }).then(value => { if (active) setGrades(value); })
      .catch(reason => { if (active) setError(String(reason.message)); });
    return () => { active = false; };
  }, [semester, data.sessions]);
  return (
    <section className="grades-page">
      <header className="page-heading"><div><p className="eyebrow">GRADEBOOK</p><h1>학점 계산기</h1></div><Calculator size={26} aria-hidden="true" /></header>
      <div className="grades-toolbar">
        <label>학기<select value={semester} onChange={event => { setSemester(event.target.value); setAdding(false); }}>
          {data.timetableTerms.map(term => <option key={term.name}>{term.name}</option>)}
        </select></label>
        {grades && <label>평점 기준<select aria-label="평점 기준" value={grades.scale} disabled={pending} onChange={event => {
          setPending(true);
          void mutate("grades.scale", { semester, scale: event.target.value }).then(refresh).catch(() => {}).finally(() => setPending(false));
        }}>{["4.5", "4.3", "4.0"].map(scale => <option key={scale}>{scale}</option>)}</select></label>}
        <button className="button primary" type="button" onClick={() => setAdding(value => !value)}><Plus size={16} />과목 추가</button>
      </div>
      {!data.timetableConfigured && <p className="muted">시간표에서 학기를 설정하면 자동으로 연결됩니다.</p>}
      {error && <p role="alert">{error}</p>}
      {grades && <>
        <div className="grade-summary" aria-label="학점 계산 결과">
          <article><span>평점평균</span><strong>{grades.summary.gpa ?? "—"}<small> / {grades.scale}</small></strong></article>
          <article><span>취득 학점</span><strong>{grades.summary.earned_credits}<small> 학점</small></strong></article>
          <article><span>평점 산입</span><strong>{grades.summary.graded_credits}<small> 학점</small></strong></article>
          <article><span>성적 미입력</span><strong>{grades.summary.pending}<small> 과목</small></strong></article>
        </div>
        <p className="grade-policy">P는 취득 학점에 포함됩니다. P와 NP는 평점평균에서 제외됩니다.</p>
        {adding && <form className="grade-add" onSubmit={event => {
          event.preventDefault();
          if (pending) return;
          setPending(true);
          void mutate("grades.save", { semester, title, credits: 3, grade: "", category: "일반", excluded: false })
            .then(refresh).then(() => { setTitle(""); setAdding(false); notify("과목 추가됨"); }).catch(() => {}).finally(() => setPending(false));
        }}><input aria-label="추가할 과목명" placeholder="과목명" value={title} onChange={event => setTitle(event.target.value)} maxLength={200} required autoFocus /><button className="button primary" disabled={pending}>추가</button></form>}
        <div className="grade-table">
          <div className="grade-table-head" aria-hidden="true"><span>과목</span><span>학점</span><span>성적</span><span>분류</span><span>관리</span></div>
          {grades.items.map(item => <GradeRow key={semester + item.id} item={item} grades={grades.grades} semester={semester} refresh={refresh} />)}
          {!grades.items.length && <div className="empty">시간표에 수업을 추가하거나 과목을 직접 입력하세요.</div>}
        </div>
        <details className="grade-sources"><summary>계산 기준</summary>
          <p>과목별 학점과 평점의 곱을 합산한 뒤 평점 산입 학점으로 나눕니다.</p>
          <a href="https://www.bufs.ac.kr/bbs/board.php?bo_table=university_rules&amp;wr_id=43" onClick={event => { event.preventDefault(); void rpc("app.open", { page: "grade45" }).catch(reason => notify(reason.message)); }}>4.5 기준 / 부산외대</a>{" / "}
          <a href="https://rules.yonsei.ac.kr/regulations/2a85e62f-029e-46d6-92c7-edefce6432c0" onClick={event => { event.preventDefault(); void rpc("app.open", { page: "grade43" }).catch(reason => notify(reason.message)); }}>4.3 기준 / 연세대</a>{" / "}
          <a href="https://registrar.berkeley.edu/faculty-staff-resources/grade-definitions/" onClick={event => { event.preventDefault(); void rpc("app.open", { page: "grade40" }).catch(reason => notify(reason.message)); }}>4.0 기준 / UC Berkeley</a>
        </details>
      </>}
    </section>
  );
}
