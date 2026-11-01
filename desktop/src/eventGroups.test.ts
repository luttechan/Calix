import { expect, test } from "vitest";
import { groupByCourse } from "./eventGroups";
import type { EventItem } from "./types";

test("강의명이 같아도 강의 ID별로 묶고 기존 일정 순서를 유지한다", () => {
  const rows = [
    { key: "a", course_id: 2, course_name: "수업" },
    { key: "b", course_id: 1, course_name: "수업" },
    { key: "c", course_id: 2, course_name: "수업" },
  ] as EventItem[];
  const groups = groupByCourse(rows);
  expect(groups.map((g) => g.id)).toEqual([1, 2]);
  expect(groups[1].events.map((e) => e.key)).toEqual(["a", "c"]);
  expect(rows.map((e) => e.key)).toEqual(["a", "b", "c"]);
});
