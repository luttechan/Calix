import { t, useLanguage } from "./i18n";
import { useState } from "react";
import { createPortal } from "react-dom";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { Modal } from "./App";
import {
  dateKey,
  dueText,
  localInput,
  monthGrid,
  monthTitle,
  shiftMonth,
  weekdays,
} from "./dates";

const clockOptions = Array.from({ length: 60 }, (_, index) =>
  String(index).padStart(2, "0"),
);

function validDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    Number(value.slice(0, 4)) >= 1900 &&
    !Number.isNaN(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value
  );
}

export function ChecklistDeadline({
  value,
  onCommit,
}: {
  value: string | null;
  onCommit: (value: string | null) => void;
}) {
  useLanguage();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <>
      <button
        type="button"
        className={`cell-value checklist-deadline${value ? "" : " cell-empty"}`}
        aria-label={t("기한")}
        title={dueText(value)}
        onClick={() => setOpen(true)}
      >
        <CalendarDays size={15} aria-hidden="true" />
        <span>{dueText(value)}</span>
      </button>
      {open && (
        <DateEditor
          title={t("기한")}
          value={localInput(value)}
          withTime
          allowClear
          onClose={close}
          onSave={(next) => {
            onCommit(next ? `${next}:00+09:00` : null);
            close();
          }}
        />
      )}
    </>
  );
}

export function DateField({
  label,
  name,
  value,
  defaultValue = "",
  withTime = false,
  allowClear = false,
  disabled = false,
  onChange,
}: {
  label: string;
  name?: string;
  value?: string;
  defaultValue?: string;
  withTime?: boolean;
  allowClear?: boolean;
  disabled?: boolean;
  onChange?: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [stored, setStored] = useState(defaultValue);
  const selected = value ?? stored;
  const close = () => setOpen(false);
  const displayed = selected
    ? selected.slice(0, 10).split("-").map(Number).join(". ") +
      (withTime ? ` ${selected.slice(11, 16)}` : "")
    : withTime
      ? "기한 없음"
      : "날짜 선택";
  return (
    <>
      {name && <input type="hidden" name={name} value={selected} />}
      <button
        type="button"
        className="date-field"
        aria-label={label}
        aria-haspopup="dialog"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        <CalendarDays size={16} aria-hidden="true" />
        <span>{displayed}</span>
      </button>
      {open && (
        <DateEditor
          title={label}
          value={selected}
          withTime={withTime}
          allowClear={allowClear}
          onClose={close}
          onSave={(next) => {
            if (value === undefined) setStored(next);
            onChange?.(next);
            close();
          }}
        />
      )}
    </>
  );
}

function DateEditor({
  title,
  value,
  withTime,
  allowClear,
  onClose,
  onSave,
}: {
  title: string;
  value: string;
  withTime: boolean;
  allowClear: boolean;
  onClose: () => void;
  onSave: (value: string) => void;
}) {
  useLanguage();
  const today = dateKey();
  const [date, setDate] = useState(value.slice(0, 10));
  const [month, setMonth] = useState((value || today).slice(0, 7));
  const [hour, setHour] = useState(value.slice(11, 13) || "23");
  const [minute, setMinute] = useState(value.slice(14, 16) || "59");
  const [year, number] = month.split("-").map(Number);
  const pick = (next: string) => {
    setDate(next);
    setMonth(next.slice(0, 7));
  };
  const valid = validDate(date);
  // Move the editor form outside the containing event form.
  return createPortal(
    <Modal title={title} onClose={onClose} className="deadline-editor">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (valid) onSave(withTime ? `${date}T${hour}:${minute}` : date);
        }}
      >
        <div className="deadline-calendar-nav">
          <button
            type="button"
            className="icon-button"
            aria-label={t("이전 달")}
            disabled={month <= "1900-01"}
            onClick={() => setMonth(shiftMonth(month, -1))}
          >
            <ChevronLeft size={18} />
          </button>
          <strong aria-live="polite">
            {monthTitle(year, number)}</strong>
          <button
            type="button"
            className="icon-button"
            aria-label={t("다음 달")}
            disabled={month >= "9999-12"}
            onClick={() => setMonth(shiftMonth(month, 1))}
          >
            <ChevronRight size={18} />
          </button>
        </div>
        <div className="deadline-calendar-days" aria-label={t("날짜 선택")}>
          {weekdays.map((day) => (
            <span key={day}>{t(day)}</span>
          ))}
          {monthGrid(month).map((day) => (
            <button
              type="button"
              key={day}
              aria-label={day}
              aria-pressed={date === day}
              data-today={today === day}
              data-outside={!day.startsWith(month)}
              disabled={day < "1900-01-01" || day.length !== 10}
              onClick={() => pick(day)}
            >
              {Number(day.slice(8))}
            </button>
          ))}
        </div>
        <div
          className={`deadline-editor-fields${withTime ? "" : " date-only"}`}
        >
          <label>{t("날짜")}{" "}<input
              aria-label={withTime ? t("기한 날짜") : t("날짜 입력")}
              placeholder="YYYY-MM-DD"
              autoComplete="off"
              maxLength={10}
              value={date}
              aria-invalid={date !== "" && !valid}
              onChange={(event) => {
                const next = event.target.value;
                setDate(next);
                if (validDate(next)) setMonth(next.slice(0, 7));
              }}
            />
          </label>
          {withTime && (
            <>
              <label>{t("시")}{" "}<select
                  aria-label={t("기한 시")}
                  value={hour}
                  onChange={(event) => setHour(event.target.value)}
                >
                  {clockOptions.slice(0, 24).map((option) => (
                    <option key={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label>{t("분")}{" "}<select
                  aria-label={t("기한 분")}
                  value={minute}
                  onChange={(event) => setMinute(event.target.value)}
                >
                  {clockOptions.map((option) => (
                    <option key={option}>{option}</option>
                  ))}
                </select>
              </label>
            </>
          )}
        </div>
        <div className="dialog-actions deadline-actions">
          {allowClear && value && (
            <button
              type="button"
              className="text-button"
              onClick={() => onSave("")}
            >
              {withTime ? t("기한 삭제") : t("지우기")}
            </button>
          )}
          <button type="button" onClick={() => pick(today)}>{t("오늘")}{" "}</button>
          <button type="submit" className="primary" disabled={!valid}>{t("적용")}{" "}</button>
        </div>
      </form>
    </Modal>,
    document.body,
  );
}
