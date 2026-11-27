import { Delete } from "lucide-react";
import { useEffect, useEffectEvent, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Modal } from "./App";
import { t } from "./i18n";
import "./pin-keypad.css";

export function pinLength(mode?: string) {
  return mode === "pin4" ? 4 : mode === "pin6" ? 6 : undefined;
}

export function validPin(mode: string | undefined, value: string, required = true) {
  const length = pinLength(mode);
  return !length || (!required && !value) || (/^[0-9]+$/.test(value) && value.length === length);
}

export function PinDots({ value, length }: { value: string; length: number }) {
  return <span className="pin-dots" aria-hidden="true">
    {Array.from({ length }, (_, i) => <i key={i} data-filled={i < value.length} data-next={i === value.length || undefined} />)}
  </span>;
}

export function PinKeypad({ label, value, length, onChange, pending, invalid, autoFocus }: {
  label: string;
  value: string;
  length: number;
  onChange: (value: string) => void;
  pending?: boolean;
  invalid?: boolean;
  autoFocus?: boolean;
}) {
  const id = useId();
  const keypad = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const readKey = useEffectEvent((event: KeyboardEvent) => {
    const element = keypad.current;
    if (!element || element.closest("[inert]") || event.defaultPrevented || event.isComposing ||
        event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const target = event.target instanceof HTMLElement ? event.target : null;
    const openDialog = target?.closest("dialog[open]") ?? document.querySelector("dialog[open]");
    if (openDialog && !openDialog.contains(element)) return;
    if (target !== input.current && target?.closest("input, textarea, select, [contenteditable], [role='textbox']")) return;
    const digit = /^[0-9]$/.test(event.key) ? event.key : /^Numpad([0-9])$/.exec(event.code)?.[1];
    const erase = event.key === "Backspace" || event.key === "Delete";
    if (!digit && !erase) return;
    event.preventDefault();
    if (pending || event.repeat) return;
    if (erase) onChange(value.slice(0, -1));
    else if (digit && value.length < length) onChange(value + digit);
  });
  useEffect(() => {
    if (!autoFocus) return;
    const focus = () => {
      const element = input.current;
      if (element && !element.closest("[inert]") &&
          (!document.querySelector("dialog[open]") || element.closest("dialog[open]"))) {
        element.focus({ preventScroll: true });
      }
    };
    focus();
    document.addEventListener("calix:startup-ready", focus);
    const onFocus = () => {
      if (!document.activeElement || document.activeElement === document.body) focus();
    };
    window.addEventListener("focus", onFocus);
    const onKeyDown = (event: KeyboardEvent) => readKey(event);
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("calix:startup-ready", focus);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("keydown", onKeyDown, true);
    };
  }, [autoFocus]);
  useEffect(() => {
    if (invalid && !pending) input.current?.focus({ preventScroll: true });
  }, [invalid, pending]);
  const add = (digit: string) => { if (!pending && value.length < length) onChange(value + digit); };
  return <div ref={keypad} className="pin-keypad" data-invalid={invalid || undefined}>
    <span className="pin-caption" aria-hidden="true">{label}</span>
    <label className="pin-indicator" htmlFor={id}>
      <span className="pin-reader">
        <PinDots value={value} length={length} />
        <input ref={input} id={id} type="password" aria-label={label} value={value} inputMode="none"
          autoComplete="off" aria-invalid={invalid || undefined} maxLength={length}
          disabled={pending} autoFocus={autoFocus}
          onChange={event => onChange(event.target.value.replace(/[^0-9]/g, "").slice(0, length))} />
      </span>
    </label>
    <div className="pin-keys" role="group" aria-label={t("숫자 키패드")}>
      {["1","2","3","4","5","6","7","8","9","0"].map(digit => <button key={digit} type="button"
        className="pin-key" disabled={pending} onPointerDown={event => event.preventDefault()}
        onClick={event => { add(digit); if (event.detail) input.current?.focus({ preventScroll: true }); }}>{digit}</button>)}
      <button type="button" className="icon-button pin-delete" aria-label={t("마지막 숫자 지우기")}
        title={t("마지막 숫자 지우기")} disabled={pending || !value}
        onPointerDown={event => event.preventDefault()} onClick={event => {
          onChange(value.slice(0, -1));
          if (event.detail) input.current?.focus({ preventScroll: true });
        }}><Delete size={21} aria-hidden="true" /></button>
    </div>
  </div>;
}

export function PinField({ title, value, length, onChange }: {
  title: string; value: string; length: number; onChange: (value: string) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  return <div className="pin-field">
    <span>{title}</span>
    <button type="button" aria-label={title} aria-haspopup="dialog" aria-expanded={draft !== null}
      onClick={() => setDraft("")}>
      <PinDots value={value} length={length} />
    </button>
    {draft !== null && createPortal(
      <Modal title={title} className="pin-dialog" onClose={() => setDraft(null)}>
        <form onSubmit={event => {
          event.preventDefault();
          event.stopPropagation();
          if (draft.length !== length && draft.length !== 0) return;
          onChange(draft);
          setDraft(null);
        }}>
          <PinKeypad label={t("PIN")} value={draft} length={length} autoFocus onChange={next => {
            if (next.length === length) {
              onChange(next);
              setDraft(null);
            } else {
              setDraft(next);
            }
          }} />
          <div className="dialog-actions">
            <button type="button" onClick={() => setDraft(null)}>{t("취소")}</button>
            <button type="submit" className="primary" disabled={draft.length !== length && draft.length !== 0}>{t("확인")}</button>
          </div>
        </form>
      </Modal>, document.body,
    )}
  </div>;
}
