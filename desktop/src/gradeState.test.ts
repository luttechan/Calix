import { expect, test } from "vitest";
import {
  changeCount,
  createSheet,
  creditValue,
  previewGrades,
  validateSheet,
  type GradeData,
} from "./gradeState";
const data: GradeData = {
  semester: "2026학년도 2학기",
  scale: "4.5",
  revision: "test",
  grades: [],
  items: [
    {
      id: "one",
      title: "과목",
      credits: 3,
      grade: "A+",
      category: "전공",
      excluded: 0,
      linked: false,
    },
  ],
  summary: {
    gpa: "4.50",
    graded_credits: 3,
    earned_credits: 3,
    registered_credits: 3,
    pending: 0,
  },
};
test("live weighted GPA uses half-up decimal rounding, P/NP and exclusions", () => {
  const sheet = createSheet(data);
  sheet.items.push(
    { ...sheet.items[0], id: "two", credits: "2", grade: "B" },
    { ...sheet.items[0], id: "p", credits: "2", grade: "P" },
    { ...sheet.items[0], id: "np", credits: "3", grade: "NP" },
    { ...sheet.items[0], id: "f", grade: "F", excluded: 1 },
  );
  expect(previewGrades(sheet)).toEqual({
    gpa: "3.90",
    graded_credits: 5,
    earned_credits: 7,
    registered_credits: 10,
    pending: 0,
  });
  sheet.scale = "4.3";
  expect(previewGrades(sheet).gpa).toBe("3.78");
  sheet.scale = "4.0";
  expect(previewGrades(sheet).gpa).toBe("3.60");
  sheet.items[0].credits = "";
  expect(previewGrades(sheet).gpa).toBe(null);
});
test("empty credit is invalid and dirty, decimal half credits are supported", () => {
  const sheet = createSheet(data);
  expect(changeCount(sheet)).toBe(0);
  sheet.items[0].credits = "3.0";
  expect(changeCount(sheet)).toBe(0);
  sheet.items[0].credits = "";
  expect(changeCount(sheet)).toBe(1);
  expect(validateSheet(sheet).one.credits).toBeTruthy();
  expect(creditValue(".5")).toBe(0.5);
  expect(creditValue("12.5")).toBe(12.5);
  for (const value of ["", "NaN", "1e1", "-1", "30.5", "1.1"])
    expect(creditValue(value)).toBeNull();
});
test("unsupported scale choices remain visible and need correction before saving", () => {
  const sheet = createSheet(data);
  sheet.items[0].grade = "A-";
  expect(validateSheet(sheet).one.grade).toBeTruthy();
  expect(sheet.items[0].grade).toBe("A-");
  sheet.scale = "4.3";
  expect(validateSheet(sheet)).toEqual({});
  expect(previewGrades(sheet).gpa).toBe("3.70");
});
