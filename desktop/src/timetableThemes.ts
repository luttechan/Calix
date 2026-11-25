import type { Session, TimetableAppearance, TimetableColors } from "./types";

type Theme = { label: string; surface: string; accent: string; hues: number[]; dark: boolean };
export const timetableThemes: Theme[] = [
  { label: "시간표 테마 오로라", surface: "#171c2d", accent: "#b6a3f2", hues: [282, 195, 160, 330, 215, 32, 256, 130], dark: true },
  { label: "시간표 테마 새벽", surface: "#fff3ef", accent: "#a45573", hues: [348, 28, 274, 18, 315, 44, 220, 162], dark: false },
  { label: "시간표 테마 조수", surface: "#edf8fb", accent: "#207b92", hues: [195, 221, 165, 242, 139, 274, 31, 321], dark: false },
  { label: "시간표 테마 자정", surface: "#151b2c", accent: "#9aa7ff", hues: [234, 196, 276, 319, 166, 28, 355, 86], dark: true },
  { label: "시간표 테마 장미", surface: "#fff1f5", accent: "#ad4871", hues: [340, 20, 291, 357, 310, 35, 200, 157], dark: false },
  { label: "시간표 테마 라벤더", surface: "#f6f1fd", accent: "#7855aa", hues: [273, 320, 228, 145, 299, 30, 191, 357], dark: false },
  { label: "시간표 테마 민트", surface: "#edf9f3", accent: "#287856", hues: [151, 183, 112, 219, 82, 270, 33, 320], dark: false },
  { label: "시간표 테마 숲", surface: "#1b2921", accent: "#a7cb84", hues: [91, 151, 45, 183, 119, 25, 209, 320], dark: true },
  { label: "시간표 테마 모래", surface: "#faf4e8", accent: "#98662f", hues: [33, 54, 17, 143, 75, 200, 341, 268], dark: false },
  { label: "시간표 테마 호박색", surface: "#fff5dd", accent: "#96600b", hues: [40, 23, 64, 352, 92, 186, 285, 140], dark: false },
  { label: "시간표 테마 테라코타", surface: "#faede6", accent: "#a45137", hues: [17, 354, 46, 125, 326, 187, 254, 74], dark: false },
  { label: "시간표 테마 오디", surface: "#2b1e30", accent: "#e1a4cf", hues: [315, 271, 354, 20, 227, 163, 191, 50], dark: true },
  { label: "시간표 테마 슬레이트", surface: "#eef2f6", accent: "#546980", hues: [215, 192, 260, 155, 316, 26, 345, 90], dark: false },
  { label: "시간표 테마 먹색", surface: "#202228", accent: "#b4bac7", hues: [217, 278, 166, 37, 331, 193, 113, 10], dark: true },
  { label: "시간표 테마 라임", surface: "#f6f8e6", accent: "#617521", hues: [78, 133, 51, 178, 107, 29, 223, 313], dark: false },
  { label: "시간표 테마 종이", surface: "#f7f5f0", accent: "#786d65", hues: [26, 210, 155, 289, 352, 78, 185, 239], dark: false },
];

export const defaultTimetableColors: TimetableColors = {
  base: { theme: 0, mode: "manual", colors: {}, slots: [] },
  terms: {},
  presets: {},
};

export function timetableCourseKey(session: Session) {
  return session.course_id > 0 ? `course:${session.course_id}` : `title:${session.title.trim().slice(0, 200)}`;
}

export function timetablePalette(index: number): string[] {
  const theme = timetableThemes[index];
  const lightness = theme.dark ? 0.68 : 0.43;
  const chroma = theme.dark ? 0.22 : 0.19;
  return theme.hues.map(hue => {
    const channel = (offset: number) => {
      const wave = (offset + hue / 30) % 12;
      const value = lightness - chroma * Math.max(-1, Math.min(wave - 3, 9 - wave, 1));
      return Math.round(255 * value).toString(16).padStart(2, "0");
    };
    return `#${channel(0)}${channel(8)}${channel(4)}`;
  });
}

export function timetableCourseColor(session: Session, slot: number, style: TimetableAppearance, palette: string[]) {
  if (style.mode === "manual") return session.color || palette[slot];
  if (style.mode === "custom") {
    return style.colors[timetableCourseKey(session)] || style.slots[slot] || palette[slot];
  }
  return palette[slot];
}
