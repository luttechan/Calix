import { useId, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { flushSync } from "react-dom";

type Props = {
  value: string | number | null;
  label: string;
  display?: string;
  type?: "text" | "datetime-local";
  suggestions?: readonly string[];
  maxLength?: number;
  options?: { value: number; label: string }[];
  color?: string;
  onCommit: (value: string | number | null) => void;
};

const styledSuggestions = typeof HTMLElement !== "undefined" &&
  "showPopover" in HTMLElement.prototype && CSS.supports("position-anchor: --field");

export function InlineCell({
  value, label, display, type = "text", suggestions, maxLength = 200, options, color, onCommit,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [active, setActive] = useState(-1);
  const id = useId();
  const anchor = `--cell-anchor-${id.replace(/[^a-z0-9_-]/gi, "-")}`;
  const input = useRef<HTMLInputElement>(null);
  const displayButton = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const cancelled = useRef(false);
  const saved = String(value ?? "");
  const search = draft === saved ? "" : draft.trim().toLocaleLowerCase();
  const matches = editing && styledSuggestions && suggestions
    ? suggestions.filter((item) => item.toLocaleLowerCase().includes(search))
    : [];
  const open = matches.length > 0;

  useLayoutEffect(() => {
    if (!open) return;
    const list = popup.current;
    if (!list) return;
    list.showPopover();
    return () => { if (list.matches(":popover-open")) list.hidePopover(); };
  }, [open]);
  useLayoutEffect(() => {
    popup.current?.children[active]?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (options)
    return (
      <select aria-label={label} className="inline-status" value={value ?? ""} title={display}
        style={{ "--status-color": color } as CSSProperties}
        onChange={(event) => onCommit(Number(event.target.value))}>
        {!options.some((option) => option.value === value) && <option value={value ?? ""}>{display || "—"}</option>}
        {options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
      </select>
    );

  const focusDisplay = () => requestAnimationFrame(() => displayButton.current?.focus({ preventScroll: true }));
  const finish = (next: string, restoreFocus = false) => {
    if (cancelled.current) return;
    cancelled.current = true;
    setEditing(false);
    if (next !== saved) onCommit(next || null);
    if (restoreFocus) focusDisplay();
  };
  const begin = () => {
    cancelled.current = false;
    flushSync(() => {
      setDraft(saved);
      setActive(-1);
      setEditing(true);
    });
    input.current?.focus();
    if (type === "datetime-local") {
      try { input.current?.showPicker(); } catch { /* Keep the focused input available. */ }
    }
  };

  if (!editing)
    return (
      <button ref={displayButton} type="button" className={`cell-value ${value ? "" : "cell-empty"}`}
        aria-label={label} title={display || saved} onClick={begin}>
        {display || saved || "—"}
      </button>
    );

  const keys = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.nativeEvent.isComposing) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      cancelled.current = true;
      setEditing(false);
      focusDisplay();
    } else if (event.key === "Enter") {
      event.preventDefault();
      finish(matches[active] ?? draft, true);
    } else if (open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      event.preventDefault();
      const next = active + (event.key === "ArrowDown" ? 1 : -1);
      setActive(next < 0 ? matches.length - 1 : next % matches.length);
    }
  };
  const custom = styledSuggestions && Boolean(suggestions?.length);
  return (
    <>
      <input ref={input} aria-label={label} type={type} value={draft} maxLength={maxLength}
        className={custom ? "cell-suggestion-editor" : undefined}
        style={custom ? { "--cell-anchor": anchor } as CSSProperties : undefined}
        role={custom ? "combobox" : undefined} aria-autocomplete={custom ? "list" : undefined}
        aria-expanded={custom ? open : undefined} aria-controls={open ? id : undefined}
        aria-activedescendant={open && matches[active] ? `${id}-${active}` : undefined}
        list={!styledSuggestions && suggestions?.length ? id : undefined}
        onChange={(event) => { setDraft(event.target.value); setActive(-1); }}
        onKeyDown={keys} onBlur={() => finish(draft)} />
      {open && (
        <div ref={popup} id={id} role="listbox" aria-label={`${label} 제안`} popover="manual"
          className="cell-suggestions" style={{ "--cell-anchor": anchor } as CSSProperties}>
          {matches.map((item, index) => (
            <div key={item} id={`${id}-${index}`} role="option" aria-selected={active === index}
              onPointerMove={() => setActive(index)} onPointerDown={(event) => event.preventDefault()}
              onClick={() => finish(item, true)}>{item}</div>
          ))}
        </div>
      )}
      {!styledSuggestions && Boolean(suggestions?.length) && (
        <datalist id={id}>{suggestions?.map((item) => <option key={item} value={item} />)}</datalist>
      )}
    </>
  );
}
