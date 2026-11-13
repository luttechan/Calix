export type GradeItem = {
  id: string;
  title: string;
  credits: number;
  grade: string;
  category: string;
  excluded: number;
  linked: boolean;
};
export type GradeSummary = {
  gpa: string | null;
  graded_credits: number;
  earned_credits: number;
  registered_credits: number;
  pending: number;
};
export type GradeData = {
  semester: string;
  scale: string;
  revision: string;
  grades: string[];
  items: GradeItem[];
  summary: GradeSummary;
};
export type GradeDraft = Omit<GradeItem, "credits"> & { credits: string };
export type GradeField =
  "title" | "credits" | "grade" | "category" | "excluded";
export type GradeErrors = Record<string, Partial<Record<GradeField, string>>>;
export type GradeSheet = {
  base: GradeData;
  scale: string;
  items: GradeDraft[];
  deleted: GradeDraft[];
};
export const GRADE_POINTS: Record<string, Record<string, number>> = {
  "4.5": {
    "A+": 45,
    A: 40,
    "B+": 35,
    B: 30,
    "C+": 25,
    C: 20,
    "D+": 15,
    D: 10,
    F: 0,
  },
  "4.3": {
    "A+": 43,
    A: 40,
    "A-": 37,
    "B+": 33,
    B: 30,
    "B-": 27,
    "C+": 23,
    C: 20,
    "C-": 17,
    "D+": 13,
    D: 10,
    "D-": 7,
    F: 0,
  },
  "4.0": {
    "A+": 40,
    A: 40,
    "A-": 37,
    "B+": 33,
    B: 30,
    "B-": 27,
    "C+": 23,
    C: 20,
    "C-": 17,
    "D+": 13,
    D: 10,
    "D-": 7,
    F: 0,
  },
};
export const gradeOptions = (scale: string) => [
  ...Object.keys(GRADE_POINTS[scale]),
  "P",
  "NP",
];
export function creditValue(text: string): number | null {
  if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(text.trim())) return null;
  const value = Number(text);
  return Number.isFinite(value) &&
    value >= 0 &&
    value <= 30 &&
    Number.isInteger(value * 2)
    ? value
    : null;
}
export const createSheet = (data: GradeData): GradeSheet => ({
  base: data,
  scale: data.scale,
  items: data.items.map((item) => ({ ...item, credits: String(item.credits) })),
  deleted: [],
});
export function changedItems(sheet: GradeSheet) {
  const before = new Map(sheet.base.items.map((item) => [item.id, item]));
  return sheet.items.filter((item) => {
    const base = before.get(item.id);
    return (
      !base ||
      (!item.linked && item.title.trim() !== base.title) ||
      creditValue(item.credits) !== base.credits ||
      item.grade !== base.grade ||
      item.category !== base.category ||
      !!item.excluded !== !!base.excluded
    );
  });
}
export const changeCount = (sheet: GradeSheet) =>
  changedItems(sheet).length +
  sheet.deleted.filter((item) =>
    sheet.base.items.some((base) => base.id === item.id),
  ).length +
  Number(sheet.scale !== sheet.base.scale);
export function validateSheet(sheet: GradeSheet): GradeErrors {
  const errors: GradeErrors = {};
  for (const item of sheet.items) {
    const error: GradeErrors[string] = {};
    if (
      !item.title.trim() ||
      item.title.length > 200 ||
      /[\u0000-\u001f]/.test(item.title)
    )
      error.title = "과목명을 입력하세요.";
    if (creditValue(item.credits) === null)
      error.credits = "학점은 0~30, 0.5 단위로 입력하세요.";
    if (!["", ...gradeOptions(sheet.scale)].includes(item.grade))
      error.grade = "현재 기준의 성적을 선택하세요.";
    if (!["전공", "교양", "일반"].includes(item.category))
      error.category = "분류를 선택하세요.";
    if (Object.keys(error).length) errors[item.id] = error;
  }
  return errors;
}
export function previewGrades(sheet: GradeSheet): GradeSummary {
  let weighted = 0,
    graded = 0,
    earned = 0,
    registered = 0,
    pending = 0,
    invalid = false;
  for (const item of sheet.items) {
    if (item.excluded) continue;
    const credits = creditValue(item.credits);
    if (credits === null) {
      pending++;
      invalid = true;
      continue;
    }
    registered += credits * 2;
    if (item.grade === "P") {
      earned += credits * 2;
      continue;
    }
    if (item.grade === "NP") continue;
    const points = GRADE_POINTS[sheet.scale][item.grade];
    if (points === undefined) {
      pending++;
      continue;
    }
    graded += credits * 2;
    weighted += credits * 2 * points;
    if (item.grade !== "F") earned += credits * 2;
  }
  const hundredths = graded
    ? Math.floor((weighted * 20 + graded) / (graded * 2))
    : null;
  return {
    gpa: !invalid && hundredths !== null ? (hundredths / 100).toFixed(2) : null,
    graded_credits: graded / 2,
    earned_credits: earned / 2,
    registered_credits: registered / 2,
    pending,
  };
}
