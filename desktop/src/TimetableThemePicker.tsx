import { Check, Moon, Palette, Sun } from "lucide-react";
import { useState, type CSSProperties } from "react";
import { Modal } from "./App";
import { t, useLanguage } from "./i18n";
import { timetablePalette, timetableThemes } from "./timetableThemes";
import type { TimetableAppearance, TimetableColors } from "./types";
import "./timetable-picker.css";

function ThemeSwatch({ theme, slots }: Pick<TimetableAppearance, "theme"> & { slots?: string[] }) {
  const surface = timetableThemes[theme].surface;
  const [first, second, third] = slots?.length ? slots : timetablePalette(theme);
  return <span
    className="timetable-swatch"
    aria-hidden="true"
    style={{
      "--swatch-surface": surface,
      "--swatch-first": first,
      "--swatch-second": second,
      "--swatch-third": third,
    } as CSSProperties}
  />;
}

const groups = [
  { title: "BRIGHT THEME", dark: false, Icon: Sun },
  { title: "DARK THEME", dark: true, Icon: Moon },
] as const;

export function TimetableThemePicker({ style, recommended, presets, selectedPreset, pending, onSelect }: {
  style: TimetableAppearance;
  recommended: number;
  presets: TimetableColors["presets"];
  selectedPreset: string;
  pending: boolean;
  onSelect: (style: TimetableAppearance) => Promise<void>;
}) {
  useLanguage();
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState<{ name: string; style: TimetableAppearance } | null>(null);
  const heading = t("시간표 테마");
  const prefersDark = timetableThemes[recommended].dark;
  const themeOrder = [recommended, ...[...timetableThemes.keys()].filter(index => index !== recommended)];
  const close = () => { setConfirmation(null); setOpen(false); };
  const activeName = selectedPreset || (style.mode === "auto" ? t(timetableThemes[style.theme].label) :
    style.mode === "custom" ? t("사용자 지정") : heading);
  const apply = (next: TimetableAppearance) => void onSelect(next).then(close).catch(() => {});
  const choose = (name: string, next: TimetableAppearance, selected: boolean) => {
    if (pending) return;
    if (selected) { close(); return; }
    if (timetableThemes[next.theme].dark !== prefersDark) {
      setConfirmation({ name, style: next });
      return;
    }
    apply(next);
  };
  const option = (key: string | number, name: string, next: TimetableAppearance, selected: boolean) =>
    <button key={key} type="button" className="timetable-theme-option"
      aria-pressed={selected} aria-disabled={pending || undefined} title={name}
      onClick={() => choose(name, next, selected)}>
      <ThemeSwatch theme={next.theme} slots={next.mode === "custom" ? next.slots : undefined} />
      <span className="timetable-theme-label">
        <span className="timetable-theme-name">{name}</span>
        {key === recommended && <small>{t("추천")}</small>}
      </span>
      {selected && <Check size={15} className="timetable-theme-check" aria-hidden="true" />}
    </button>;
  return <>
    <button type="button" className="icon-button timetable-theme-trigger" aria-label={heading}
      aria-haspopup="dialog" aria-expanded={open} data-tooltip={activeName === heading ? heading : `${heading} (${activeName})`} disabled={pending && !open} onClick={() => setOpen(true)}>
      {style.mode === "manual" ? <Palette size={16} aria-hidden="true" /> :
        <ThemeSwatch theme={style.theme} slots={style.mode === "custom" ? style.slots : undefined} />}
    </button>
    {open && <Modal title={heading} className="timetable-theme-dialog" onClose={close}>
      {confirmation ? <div className="timetable-theme-confirmation">
        <ThemeSwatch theme={confirmation.style.theme} slots={confirmation.style.slots} />
        <p role="status">{t("시간표 테마를 ‘{0}’(으)로 바꿀까요?", [confirmation.name])}</p>
        <div className="dialog-actions">
          <button type="button" disabled={pending} onClick={() => setConfirmation(null)}>{t("취소")}</button>
          <button type="button" className="primary" autoFocus disabled={pending} onClick={() => apply(confirmation.style)}>{t("변경")}</button>
        </div>
      </div> : <div className="timetable-theme-groups" aria-busy={pending}>
        {(prefersDark ? [...groups].reverse() : groups).map(({ title, dark, Icon }) => <section key={title} aria-label={title}>
          <h3 lang="en"><Icon size={15} aria-hidden="true" />{title}</h3>
          <div className="timetable-theme-options">
            {themeOrder.filter(index => timetableThemes[index].dark === dark).map(index =>
              option(index, t(timetableThemes[index].label), { ...style, theme: index, mode: "auto" },
                style.mode === "auto" && style.theme === index))}
          </div>
        </section>)}
        {Object.keys(presets).length > 0 && <section aria-label={t("저장한 시간표 테마")}>
          <h3><Palette size={15} aria-hidden="true" />{t("저장한 시간표 테마")}</h3>
          <div className="timetable-theme-options">
            {Object.entries(presets).map(([name, preset]) => option(name, name, preset, name === selectedPreset))}
          </div>
        </section>}
      </div>}
    </Modal>}
  </>;
}
