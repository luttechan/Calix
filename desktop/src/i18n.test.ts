import { afterEach, describe, expect, it } from "vitest";
import { locale, semesterName, setLanguage, t } from "./i18n";
import { dateKey, monthName } from "./dates";

afterEach(() => setLanguage("ko"));

describe("interface language", () => {
  it("switches locale and formats messages while preserving the semester identifier", () => {
    const semester = "2026학년도 2학기";
    setLanguage("en");
    expect(t("다가오는 마감")).toBe("Upcoming deadlines");
    expect(t("{0}일 전", [4])).toBe("4 d left");
    expect(semesterName(semester)).toBe("Fall semester 2026");
    expect(monthName(11)).toBe("Nov");
    setLanguage("ja");
    expect(locale()).toBe("ja-JP");
    expect(t("다가오는 마감")).toBe("今後の締切");
    expect(semesterName(semester)).toBe("2026年度 後期");
    expect(semesterName("직접 설정한 학기")).toBe("직접 설정한 학기");
    expect(dateKey("2026-11-20T22:00:00Z")).toBe("2026-11-21");
  });

  it("falls back to Korean for invalid language values", () => {
    setLanguage("en");
    expect(t("지원되지 않는 키")).toBe("지원되지 않는 키");
    expect(t("toString")).toBe("toString");
    setLanguage("fr");
    expect(locale()).toBe("ko-KR");
    expect(t("달력")).toBe("달력");
  });
});
