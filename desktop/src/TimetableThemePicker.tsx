import { Check, ChevronDown, Moon, Palette, Sun } from "lucide-react";
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

export function TimetableThemePicker({ style, presets, selectedPreset, pending, onSelect }: {
  style: TimetableAppearance;
  presets: TimetableColors["presets"];
  selectedPreset: string;
  pending: boolean;
  onSelect: (style: TimetableAppearance) => Promise<void>;
}) {
  useLanguage();
  const [open, setOpen] = useState(false);
  const heading = t("시간표 테마");
  const activeName = selectedPreset || (style.mode === "auto" ? t(timetableThemes[style.theme].label) :
    style.mode === "custom" ? t("사용자 지정") : heading);
  const choose = (next: TimetableAppearance, selected: boolean) => {
    if (pending) return;
    if (selected) { setOpen(false); return; }
    void onSelect(next).then(() => setOpen(false)).catch(() => {});
  };
  const option = (key: string | number, name: string, next: TimetableAppearance, selected: boolean) =>
    <button key={key} type="button" className="timetable-theme-option"
      aria-pressed={selected} aria-disabled={pending || undefined} title={name}
      onClick={() => choose(next, selected)}>
      <ThemeSwatch theme={next.theme} slots={next.mode === "custom" ? next.slots : undefined} />
      <span className="timetable-theme-name">{name}</span>
      {selected && <Check size={15} className="timetable-theme-check" aria-hidden="true" />}
    </button>;
  return <>
    <button type="button" className="timetable-theme-trigger" aria-label={heading}
      aria-haspopup="dialog" aria-expanded={open} title={activeName} disabled={pending && !open} onClick={() => setOpen(true)}>
      {style.mode === "manual" ? <Palette size={16} aria-hidden="true" /> :
        <ThemeSwatch theme={style.theme} slots={style.mode === "custom" ? style.slots : undefined} />}
      <span>{activeName}</span>
      <ChevronDown size={14} aria-hidden="true" />
    </button>
    {open && <Modal title={heading} className="timetable-theme-dialog" onClose={() => setOpen(false)}>
      <div className="timetable-theme-groups" aria-busy={pending}>
        {groups.map(({ title, dark, Icon }) => <section key={title} aria-label={title}>
          <h3 lang="en"><Icon size={15} aria-hidden="true" />{title}</h3>
          <div className="timetable-theme-options">
            {timetableThemes.map((theme, index) => theme.dark === dark &&
              option(index, t(theme.label), { ...style, theme: index, mode: "auto" },
                style.mode === "auto" && style.theme === index))}
          </div>
        </section>)}
        {Object.keys(presets).length > 0 && <section aria-label={t("저장한 시간표 테마")}>
          <h3><Palette size={15} aria-hidden="true" />{t("저장한 시간표 테마")}</h3>
          <div className="timetable-theme-options">
            {Object.entries(presets).map(([name, preset]) => option(name, name, preset, name === selectedPreset))}
          </div>
        </section>}
      </div>
    </Modal>}
  </>;
}
