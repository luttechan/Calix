import { useState } from "react";
import { useCalix } from "./App";
import { studyPlan, busyDates, freeSlots } from "./planningState";
import type { Session } from "./types";
export function PlanningPanel({ now }: { now: Date }) {
  const { data, openEvent } = useCalix();
  const [budget, setBudget] = useState(60),
    [minutes, setMinutes] = useState(30);
  const plan = studyPlan(data.events, now, budget, minutes),
    crowded = busyDates(data.events, now);
  return (
    <div className="deadline-grid planning-panel">
      <article className="overview-card">
        <h2>오늘의 학습 계획</h2>
        <div className="overview-tools">
          <label>
            학습 시간
            <select
              aria-label="학습 시간"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            >
              {[30, 60, 90, 120, 180].map((n) => (
                <option key={n} value={n}>
                  {n}분
                </option>
              ))}
            </select>
          </label>
          <label>
            항목당 예상
            <select
              aria-label="항목당 예상 시간"
              value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}
            >
              {[15, 30, 45, 60].map((n) => (
                <option key={n} value={n}>
                  {n}분
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="muted">
          마감 순으로 {plan.length}개 · 예상 {plan.length * minutes}분
        </p>
        <div className="overview-items">
          {plan.map((e, i) => (
            <button key={e.key} onClick={() => openEvent(e.key)}>
              <span>{i + 1}</span>
              <span>
                <strong>{e.title}</strong>
                <small>{e.course_name}</small>
              </span>
            </button>
          ))}
        </div>
        {!plan.length && <p>{budget < minutes && studyPlan(data.events, now, minutes, minutes).length ? "학습 시간을 늘리거나 항목당 예상 시간을 줄이세요." : "계획할 일정이 없습니다."}</p>}
      </article>
      <article className="overview-card">
        <h2>마감 밀집 경고</h2>
        {crowded.length ? (
          crowded.map(([day, items]) => (
            <details key={day}>
              <summary>
                {day} · {items.length}개
              </summary>
              <div className="overview-items">
                {items.map((e) => (
                  <button key={e.key} onClick={() => openEvent(e.key)}>
                    {e.title}
                  </button>
                ))}
              </div>
            </details>
          ))
        ) : (
          <p className="muted">3개 이상 겹치는 마감이 없습니다.</p>
        )}
      </article>
    </div>
  );
}
export function FreeTimeFinder({
  sessions,
  offDays,
}: {
  sessions: Session[];
  offDays: number[];
}) {
  const [duration, setDuration] = useState(60);
  const slots = freeSlots(sessions, offDays, duration);
  const clock = (n: number) =>
    `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`;
  return (
    <details className="overview-card free-time">
      <summary>공강 찾기</summary>
      <label>
        필요한 시간
        <select
          aria-label="공강 길이"
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
        >
          {[30, 60, 90, 120, 180].map((n) => (
            <option key={n} value={n}>
              {n}분 이상
            </option>
          ))}
        </select>
      </label>
      <p className="muted">선택한 학기 시간표 기준 · 09:00–18:00</p>
      <div className="free-slots">
        {slots.map((s) => (
          <span key={`${s.day}-${s.start}`}>
            <strong>{"월화수목금토일"[s.day]}</strong> {clock(s.start)}–
            {clock(s.end)}
          </span>
        ))}
      </div>
      {!slots.length && <p>조건에 맞는 공강이 없습니다.</p>}
    </details>
  );
}
