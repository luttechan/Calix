import { Check, ChevronDown } from "lucide-react";
import { useLayoutEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { Modal } from "./App";
import { t } from "./i18n";
import { validPaletteColor } from "./themePalette";
import "./color-field.css";

const fallbackColor = "#af527f";
const swatches = ["#e0728d", "#ed9057", "#dfbd54", "#69bc88", "#4dbeb7", "#628ed8", "#a885d8", "#868d9b"];
const channels = ["R", "G", "B"];
const hueSpectrum = "linear-gradient(90deg,#f00,#ff0,#0f0,#0ff,#00f,#f0f,#f00)";
type Hsv = { hue: number; saturation: number; brightness: number };

function rgbOf(hex: string) {
  return [1, 3, 5].map(start => parseInt(hex.slice(start, start + 2), 16));
}

function hsvOf([r, g, b]: number[]): Hsv {
  const max = Math.max(r, g, b);
  const delta = max - Math.min(r, g, b);
  const turn = !delta ? 0 : max === r ? (g - b) / delta : max === g ? 2 + (b - r) / delta : 4 + (r - g) / delta;
  return { hue: (60 * turn + 360) % 360, saturation: max ? delta / max : 0, brightness: max / 255 };
}

function hexOf(rgb: number[]) {
  return "#" + rgb.map(value => Math.round(value).toString(16).padStart(2, "0")).join("");
}

function hexFromHsv({ hue, saturation, brightness }: Hsv) {
  return hexOf([5, 3, 1].map(offset => {
    const wave = (offset + hue / 60) % 6;
    return 255 * brightness * (1 - saturation * Math.max(0, Math.min(wave, 4 - wave, 1)));
  }));
}

export function ColorField({ id, label, caption, name, value, defaultValue = fallbackColor, disabled, onChange }: {
  id?: string;
  label: string;
  caption?: boolean;
  name?: string;
  value?: string;
  defaultValue?: string;
  disabled?: boolean;
  onChange?: (value: string) => void;
}) {
  const [local, setLocal] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const source = value ?? local;
  const color = validPaletteColor(source) ? source.toLowerCase() : fallbackColor;
  return <div className="color-field">
    {caption && <span className="color-field-caption">{label}</span>}
    <button ref={trigger} id={id} type="button" className="color-trigger"
      aria-label={label} title={label} aria-haspopup="dialog" aria-expanded={open}
      disabled={disabled} onClick={() => setOpen(previous => !previous)}>
      <span className="color-dot" style={{ backgroundColor: color }} aria-hidden="true" />
      <ChevronDown size={14} aria-hidden="true" />
    </button>
    {name && <input type="hidden" name={name} value={color} disabled={disabled} />}
    {open && <ColorPalette label={label} color={color} anchor={trigger} onClose={() => setOpen(false)} onChange={next => {
      if (value === undefined) setLocal(next);
      onChange?.(next);
    }} />}
  </div>;
}

function ColorPalette({ label, color, anchor, onChange, onClose }: {
  label: string;
  color: string;
  anchor: { current: HTMLButtonElement | null };
  onChange: (next: string) => void;
  onClose: () => void;
}) {
  const [hsv, setHsv] = useState(() => hsvOf(rgbOf(color)));
  const [draft, setDraft] = useState<string | null>(null);
  const popup = useRef<HTMLDivElement>(null);
  const rgb = rgbOf(color);
  const pick = (next: string) => {
    setHsv(hsvOf(rgbOf(next)));
    onChange(next);
  };
  const adjust = (next: Hsv) => {
    setHsv(next);
    onChange(hexFromHsv(next));
  };
  const fromPointer = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const axis = (position: number) => Math.max(0, Math.min(1, position));
    adjust({ ...hsv, saturation: axis((event.clientX - rect.left) / rect.width),
      brightness: axis(1 - (event.clientY - rect.top) / rect.height) });
  };
  useLayoutEffect(() => {
    const panel = popup.current;
    const button = anchor.current;
    if (!panel || !button) return;
    const position = (event?: Event) => {
      if (event?.target instanceof Node && panel.contains(event.target)) return;
      const rect = button.getBoundingClientRect();
      const below = window.innerHeight - rect.bottom;
      const top = below >= panel.offsetHeight + 8 || below >= rect.top ? rect.bottom + 6 : rect.top - panel.offsetHeight - 6;
      panel.style.top = `${Math.max(8, Math.min(top, window.innerHeight - panel.offsetHeight - 8))}px`;
      panel.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - panel.offsetWidth - 8))}px`;
    };
    panel.showPopover({ source: button });
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [anchor]);
  const body = <div className="color-picker-content">
    <div className="color-picker-plane" aria-hidden="true" style={{
      "--color-hue": `hsl(${hsv.hue} 100% 50%)`,
      "--color-x": `${hsv.saturation * 100}%`,
      "--color-y": `${(1 - hsv.brightness) * 100}%`,
    } as CSSProperties} onPointerDown={event => {
      if (event.button !== 0) return;
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      fromPointer(event);
    }} onPointerMove={event => {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) fromPointer(event);
    }} />
    <div className="color-picker-hue-row">
      <span className="color-dot" style={{ backgroundColor: color }} aria-hidden="true" />
      <input className="color-picker-hue" style={{ backgroundImage: hueSpectrum }} type="range" min={0} max={359}
        aria-label={t("색조")} value={Math.round(hsv.hue) % 360} onChange={event => adjust({ ...hsv, hue: Number(event.target.value) })} />
    </div>
    <div className="color-picker-codes" onKeyDown={event => {
      if (event.key === "Enter" && event.target instanceof HTMLInputElement) {
        event.preventDefault();
        event.target.blur();
      }
    }}>
      <label>HEX<input aria-label="HEX" value={draft ?? color.toUpperCase()} maxLength={7} spellCheck={false}
        onFocus={event => event.target.select()} onBlur={() => setDraft(null)} onChange={event => {
          const value = event.target.value;
          const next = value.startsWith("#") ? value : "#" + value;
          setDraft(value);
          if (validPaletteColor(next)) pick(next.toLowerCase());
        }} /></label>
      {channels.map((channel, index) => <RgbField key={channel} label={channel} value={rgb[index]} onChange={value => {
        const next = [...rgb];
        next[index] = value;
        pick(hexOf(next));
      }} />)}
    </div>
    <div className="color-picker-swatches" aria-label={t("추천 색상")} role="group">
      {swatches.map(swatch => <button key={swatch} type="button" style={{ backgroundColor: swatch }}
        aria-label={swatch.toUpperCase()} aria-pressed={swatch === color} title={swatch.toUpperCase()}
        onClick={() => pick(swatch)}>{swatch === color && <Check size={13} aria-hidden="true" />}</button>)}
    </div>
  </div>;
  if (!("showPopover" in HTMLElement.prototype)) {
    return <Modal title={label} onClose={onClose} className="color-picker-fallback">{body}</Modal>;
  }
  return <div ref={popup} className="color-picker" role="dialog" aria-label={label} popover="auto"
    onToggle={event => { if (event.newState === "closed") onClose(); }}>{body}</div>;
}

function RgbField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  return <label>{label}<input aria-label={label} inputMode="numeric" maxLength={3} value={draft ?? value}
    onFocus={event => event.target.select()} onBlur={() => setDraft(null)} onChange={event => {
      const digits = event.target.value.replace(/\D/g, "");
      const normalized = Math.min(Number(digits), 255);
      setDraft(digits ? String(normalized) : "");
      if (digits) onChange(normalized);
    }} /></label>;
}
