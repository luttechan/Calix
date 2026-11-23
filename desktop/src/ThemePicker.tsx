import { Check } from "lucide-react";
import { t, useLanguage } from "./i18n";
import type { ThemeId } from "./types";

export const defaultTheme = "aurora" satisfies ThemeId;

const themeGroups = [
  ["Aurora", [
    [defaultTheme, "오로라", "#79dbca", "#182e4a"],
    ["aurora-dawn", "새벽", "#c0e5f0", "#aaa2dc"],
    ["aurora-dusk", "황혼", "#c2a3f0", "#432f6c"],
  ]],
  ["Pre-Aurora", [
    ["pink", "핑크", "#d09bb7"],
    ["sky", "스카이블루", "#9bb8db"],
    ["mint", "민트", "#9bcdb9"],
    ["purple", "퍼플", "#b7a0d4"],
    ["dark", "다크", "#333242"],
    ["peach", "피치", "#deaa92"],
    ["amber", "앰버", "#d7b16a"],
    ["olive", "올리브", "#a7b580"],
    ["lavender", "라벤더", "#aaa7dc"],
  ]],
] as const satisfies readonly [string, readonly (readonly [ThemeId, string, string, string?])[]][];

export function ThemePicker({ value, onChange }: { value: ThemeId; onChange: (theme: ThemeId) => void }) {
  useLanguage();
  return (
    <div className="theme-families">
      {themeGroups.map(([family, themes]) => (
        <fieldset className="theme-family" key={family}>
          <legend lang="en">{family}</legend>
          <div className="theme-options">
            {themes.map(([id, name, color, second]) => (
              <button key={id} type="button" aria-pressed={id === value} onClick={() => onChange(id)}>
                <span className="theme-swatch" aria-hidden="true" style={{
                  background: second ? `linear-gradient(150deg, ${color}, ${second})` : color,
                }} />
                <span className="theme-label">{t(name)}</span>
                <Check size={15} className="theme-selection" aria-hidden="true" />
              </button>
            ))}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
