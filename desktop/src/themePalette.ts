import type { PaletteColor, ThemePalette } from "./types";

export const paletteTokens = [
  ["canvas", "Canvas", "--bg"],
  ["surface", "Surface", "--surface"],
  ["accent", "Accent", "--accent"],
  ["muted", "Muted", "--muted"],
] as const;

export function validPaletteColor(value: string | undefined): value is string {
  return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value);
}

export function paletteValues(style: CSSStyleDeclaration) {
  return Object.fromEntries(paletteTokens.map(([key, , token]) => {
    const value = style.getPropertyValue(token).trim();
    const color = /^#[0-9a-f]{3}$/i.test(value)
      ? `#${[...value.slice(1)].map((digit) => digit.repeat(2)).join("")}`
      : value;
    return [key, color];
  })) as Record<PaletteColor, string>;
}

export function applyThemePalette(root: HTMLElement, palette: ThemePalette = {}) {
  const apply = (name: string, value: string | undefined) => {
    if (value) root.style.setProperty(name, value);
    else root.style.removeProperty(name);
  };
  for (const [key, , token] of paletteTokens) {
    const value = palette[key];
    apply(token, validPaletteColor(value) ? value : undefined);
  }
  const accent = validPaletteColor(palette.accent);
  const surface = validPaletteColor(palette.surface);
  apply("--accent-soft", accent ? "color-mix(in srgb, var(--accent) 17%, var(--surface))" : undefined);
  apply("--halo", accent ? "color-mix(in srgb, var(--accent) 45%, var(--bg))" : undefined);
  apply("--halo2", accent ? "color-mix(in srgb, var(--accent) 23%, var(--bg))" : undefined);
  apply("--glass", surface ? "color-mix(in srgb, var(--surface) 65%, transparent)" : undefined);
  apply("--rail", surface ? "color-mix(in srgb, var(--surface) 50%, transparent)" : undefined);
}
