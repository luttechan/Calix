import { t } from "./i18n";

export const dateEras = [
  ["gregorian", "서력"], ["dangi", "단기"], ["buddhist", "불기"], ["japanese", "일본력"],
] as const;
export type DateEra = typeof dateEras[number][0];

const japaneseYear = new Intl.DateTimeFormat("ja-JP-u-ca-japanese", {
  timeZone: "UTC", era: "long", year: "numeric",
});

export function formatFullDate(isoDate: string, era: DateEra = "gregorian") {
  const dayKey = isoDate.slice(0, 10);
  const [year, month, day] = dayKey.split("-");
  if (!year || !month || !day) return dayKey;
  let displayYear = year;
  if (era === "dangi") displayYear = `${t("단기")} ${Number(year) + 2333}`;
  if (era === "buddhist") displayYear = `${t("불기")} ${Number(year) + 544}`;
  if (era === "japanese") {
    const date = new Date(dayKey + "T00:00:00Z");
    if (Number.isFinite(date.getTime())) displayYear = japaneseYear.format(date).replace(/年$/, "");
  }
  return `${displayYear} / ${month} / ${day}`;
}
