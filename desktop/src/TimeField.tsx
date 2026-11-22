import { t, useLanguage } from "./i18n";
import { useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Clock3 } from "lucide-react";
import { Modal } from "./App";
import "./time-field.css";

const pad = (value: string | number) => String(value).padStart(2, "0");
const hours = Array.from({ length: 12 }, (_, index) => index + 1);
const minutes = Array.from({ length: 60 }, (_, index) => index);
const format = (hour: number, minute: number) => `${pad(hour)}:${pad(minute)}`;
const hour12 = (hour: number) => hour % 12 || 12;

export function readTime(text: string, reference: string): string | null {
  let input = text.trim();
  const prefix = input.match(/^(오전|오후|午前|午後|AM|PM)/i);
  const period = prefix ?? input.match(/(오전|오후|午前|午後|AM|PM)$/i);
  const afternoon = /^(오후|午後|PM)$/i.test(period?.[1] ?? "");
  if (period) input = (prefix ? input.slice(period[0].length) : input.slice(0, -period[0].length)).trim();
  if (period && !input) {
    const [hour, minute] = reference.split(":").map(Number);
    return format(hour % 12 + (afternoon ? 12 : 0), minute);
  }
  const numbers = input.match(/^(\d{1,2})\s*:\s*(\d{1,2})$|^(\d{1,2})(\d{2})$/);
  if (!numbers) return null;
  const hour = Number(numbers[1] ?? numbers[3]);
  const minute = Number(numbers[2] ?? numbers[4]);
  if (minute > 59 || hour > 23 || (period && (hour < 1 || hour > 12))) return null;
  return format(period ? hour % 12 + (afternoon ? 12 : 0) : hour, minute);
}

const showTime = (value: string) => {
  const [hour, minute] = value.split(":").map(Number);
  return `${t(hour >= 12 ? "오후" : "오전")} ${format(hour12(hour), minute)}`;
};

export function TimeField({
  label,
  caption = label,
  value,
  onChange,
}: {
  label: string;
  caption?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  useLanguage();
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const anchor = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  const pick = (next: string) => {
    onChange(next);
    setDraft(null);
    input.current?.setCustomValidity("");
    close();
    input.current?.focus({ preventScroll: true });
  };
  return (
    <div className="time-control">
      <label htmlFor={id}>{caption}</label>
      <div className="time-field" ref={anchor}>
        <input
          id={id}
          ref={input}
          aria-label={label}
          aria-keyshortcuts="Alt+ArrowDown"
          value={draft ?? showTime(value)}
          autoComplete="off"
          spellCheck={false}
          required
          onFocus={(event) => event.target.select()}
          onChange={(event) => {
            const text = event.target.value.slice(0, 24);
            setDraft(text);
            const next = readTime(text, value);
            event.target.setCustomValidity(next ? "" : t("시간을 확인하세요."));
            if (next) onChange(next);
          }}
          onBlur={(event) => {
            if (readTime(event.target.value, value)) setDraft(null);
          }}
          onKeyDown={(event) => {
            if (event.altKey && event.key === "ArrowDown") {
              event.preventDefault();
              setOpen(true);
            }
          }}
        />
        <button
          type="button"
          className="time-field-trigger"
          aria-label={t("{0} 시간 선택", [String(label)])}
          aria-haspopup="dialog"
          aria-expanded={open}
          tabIndex={-1}
          onClick={() => setOpen(!open)}
        >
          <Clock3 size={17} aria-hidden="true" />
        </button>
        {open && <ClockPicker label={label} value={value} anchor={anchor} onClose={close} onPick={pick} />}
      </div>
    </div>
  );
}

function moveOption(
  event: KeyboardEvent<HTMLDivElement>,
  values: number[],
  selected: number,
  onSelect: (value: number) => void,
) {
  const current = values.indexOf(selected);
  const last = values.length - 1;
  let next;
  switch (event.key) {
    case "ArrowUp": next = Math.max(0, current - 1); break;
    case "ArrowDown": next = Math.min(last, current + 1); break;
    case "Home": next = 0; break;
    case "End": next = last; break;
    default: return;
  }
  event.preventDefault();
  onSelect(values[next]);
  event.currentTarget.querySelector<HTMLButtonElement>(`[data-option="${values[next]}"]`)?.focus();
}

function ClockPicker({
  label,
  value,
  anchor,
  onClose,
  onPick,
}: {
  label: string;
  value: string;
  anchor: { current: HTMLDivElement | null };
  onClose: () => void;
  onPick: (value: string) => void;
}) {
  useLanguage();
  const [hour, setHour] = useState(() => Number(value.slice(0, 2)));
  const [minute, setMinute] = useState(() => Number(value.slice(3, 5)));
  const popup = useRef<HTMLDivElement>(null);
  const selectHour = (next: number) => setHour(next % 12 + (hour >= 12 ? 12 : 0));
  useLayoutEffect(() => {
    const panel = popup.current;
    if (!panel) return;
    const position = (event?: Event) => {
      if (event?.target instanceof Node && panel.contains(event.target)) return;
      const rect = anchor.current?.getBoundingClientRect();
      if (!rect) return;
      const below = window.innerHeight - rect.bottom;
      const above = rect.top;
      const height = panel.offsetHeight;
      const preferredTop = below >= height + 8 || below >= above
        ? rect.bottom + 6
        : rect.top - height - 6;
      panel.style.top = `${Math.max(8, Math.min(preferredTop, window.innerHeight - height - 8))}px`;
      panel.style.left = `${Math.max(8, Math.min(rect.right - panel.offsetWidth, window.innerWidth - panel.offsetWidth - 8))}px`;
    };
    panel.showPopover();
    position();
    panel.querySelectorAll<HTMLElement>(".time-picker-options").forEach((list) => {
      const selected = list.querySelector<HTMLElement>("[aria-pressed=true]");
      if (selected) list.scrollTop = selected.offsetTop - (list.clientHeight - selected.offsetHeight) / 2;
    });
    panel.querySelector<HTMLElement>(".time-picker-period [aria-pressed=true]")?.focus({ preventScroll: true });
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [anchor]);
  const choices = (
    <>
      <div className="segmented time-picker-period" role="group" aria-label={t("오전 또는 오후")}>
        <button type="button" aria-pressed={hour < 12} className={hour < 12 ? "selected" : ""}
          onClick={() => setHour(hour % 12)}>{t("오전")}</button>
        <button type="button" aria-pressed={hour >= 12} className={hour >= 12 ? "selected" : ""}
          onClick={() => setHour(hour % 12 + 12)}>{t("오후")}</button>
      </div>
      <div className="time-picker-columns">
        <div>
          <span>{t("시")}</span>
          <div className="time-picker-options" role="group" aria-label={t("시 선택")}
            onKeyDown={(event) => moveOption(event, hours, hour12(hour), selectHour)}>
            {hours.map((value) => (
              <button type="button" key={value} aria-label={t("{0}시", [String(value)])} data-option={value}
                tabIndex={hour12(hour) === value ? 0 : -1}
                aria-pressed={hour12(hour) === value} onClick={() => selectHour(value)}>{pad(value)}</button>
            ))}
          </div>
        </div>
        <div>
          <span>{t("분")}</span>
          <div className="time-picker-options" role="group" aria-label={t("분 선택")}
            onKeyDown={(event) => moveOption(event, minutes, minute, setMinute)}>
            {minutes.map((value) => (
              <button type="button" key={value} aria-label={t("{0}분", [String(value)])} data-option={value}
                tabIndex={minute === value ? 0 : -1}
                aria-pressed={minute === value} onClick={() => setMinute(value)}>{pad(value)}</button>
            ))}
          </div>
        </div>
      </div>
      <footer className="time-picker-actions">
        <output aria-live="polite">{showTime(format(hour, minute))}</output>
        <button className="primary" type="button" onClick={() => onPick(format(hour, minute))}>{t("적용")}</button>
      </footer>
    </>
  );
  if (!("showPopover" in HTMLElement.prototype)) {
    return createPortal(
      <Modal title={t("{0} 시간 선택", [String(label)])} onClose={onClose} className="time-picker-fallback">{choices}</Modal>,
      document.body,
    );
  }
  return (
    <div ref={popup} role="dialog" aria-label={t("{0} 시간 선택", [String(label)])} popover="auto" className="time-picker"
      onToggle={(event) => { if (event.newState === "closed") onClose(); }}>
      {choices}
    </div>
  );
}
