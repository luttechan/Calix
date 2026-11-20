import { useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { Modal } from "./App";
import { dateKey, dueText, localInput, monthGrid, shiftMonth, weekdays } from "./dates";

const clockOptions = Array.from({ length: 60 }, (_, index) => String(index).padStart(2, "0"));

function validDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number(value.slice(0, 4)) >= 1900 && !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function ChecklistDeadline({ value, onCommit }: { value: string | null; onCommit: (value: string | null) => void }) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return <>
    <button type="button" className={`cell-value checklist-deadline${value ? "" : " cell-empty"}`} aria-label="기한" title={dueText(value)} onClick={() => setOpen(true)}>
      <CalendarDays size={15} aria-hidden="true" /><span>{dueText(value)}</span>
    </button>
    {open && <DeadlineEditor value={value} onClose={close} onSave={(next) => { onCommit(next); close(); }} />}
  </>;
}

function DeadlineEditor({ value, onClose, onSave }: { value: string | null; onClose: () => void; onSave: (value: string | null) => void }) {
  const initial = localInput(value);
  const today = dateKey();
  const [date, setDate] = useState(initial.slice(0, 10));
  const [month, setMonth] = useState((initial || today).slice(0, 7));
  const [hour, setHour] = useState(initial.slice(11, 13) || "23");
  const [minute, setMinute] = useState(initial.slice(14, 16) || "59");
  const [year, number] = month.split("-").map(Number);
  const pick = (next: string) => { setDate(next); setMonth(next.slice(0, 7)); };
  const valid = validDate(date);
  return <Modal title="기한" onClose={onClose} className="deadline-editor">
    <form onSubmit={(event) => { event.preventDefault(); if (valid) onSave(`${date}T${hour}:${minute}:00+09:00`); }}>
      <div className="deadline-calendar-nav">
        <button type="button" className="icon-button" aria-label="이전 달" disabled={month <= "1900-01"} onClick={() => setMonth(shiftMonth(month, -1))}><ChevronLeft size={18} /></button>
        <strong aria-live="polite">{year}년 {number}월</strong>
        <button type="button" className="icon-button" aria-label="다음 달" disabled={month >= "9999-12"} onClick={() => setMonth(shiftMonth(month, 1))}><ChevronRight size={18} /></button>
      </div>
      <div className="deadline-calendar-days" aria-label="기한 날짜 선택">
        {weekdays.map((day) => <span key={day}>{day}</span>)}
        {monthGrid(month).map((day) => <button type="button" key={day} aria-label={day} aria-pressed={date === day}
          data-today={today === day} data-outside={!day.startsWith(month)} disabled={day < "1900-01-01" || day.length !== 10}
          onClick={() => pick(day)}>{Number(day.slice(8))}</button>)}
      </div>
      <div className="deadline-editor-fields">
        <label>날짜<input aria-label="기한 날짜" placeholder="YYYY-MM-DD" autoComplete="off" maxLength={10}
          value={date} aria-invalid={date !== "" && !valid}
          onChange={(event) => { const next = event.target.value; setDate(next); if (validDate(next)) setMonth(next.slice(0, 7)); }} /></label>
        <label>시<select aria-label="기한 시" value={hour} onChange={(event) => setHour(event.target.value)}>{clockOptions.slice(0, 24).map((option) => <option key={option}>{option}</option>)}</select></label>
        <label>분<select aria-label="기한 분" value={minute} onChange={(event) => setMinute(event.target.value)}>{clockOptions.map((option) => <option key={option}>{option}</option>)}</select></label>
      </div>
      <div className="dialog-actions deadline-actions">
        {value && <button type="button" className="text-button" onClick={() => onSave(null)}>기한 삭제</button>}
        <button type="button" onClick={() => pick(today)}>오늘</button>
        <button type="submit" className="primary" disabled={!valid}>적용</button>
      </div>
    </form>
  </Modal>;
}
