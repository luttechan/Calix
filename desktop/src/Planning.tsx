import { t, useLanguage } from "./i18n";
import { useState } from "react";
import { useCalix } from "./App";
import { studyPlan, busyDates } from "./planningState";
export function PlanningPanel({ now }: { now: Date }) {
  useLanguage();
  const { data, openEvent } = useCalix();
  const [budget, setBudget] = useState(60),
    [minutes, setMinutes] = useState(30);
  const plan = studyPlan(data.events, now, budget, minutes),
    crowded = busyDates(data.events, now);
  return (
    <div className="deadline-grid planning-panel">
      <article className="overview-card">
        <h2>{t("오늘의 학습 계획")}</h2>
        <div className="plan-fields">
          <label>{t("학습 시간")}{" "}<select
              aria-label={t("학습 시간")}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            >
              {[30, 60, 90, 120, 180].map((n) => (
                <option key={n} value={n}>
                  {n}{t("분")}{" "}</option>
              ))}
            </select>
          </label>
          <label>{t("항목당 예상")}{" "}<select
              aria-label={t("항목당 예상 시간")}
              value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}
            >
              {[15, 30, 45, 60].map((n) => (
                <option key={n} value={n}>
                  {n}{t("분")}{" "}</option>
              ))}
            </select>
          </label>
        </div>
        <p className="plan-summary muted" aria-live="polite">
          {plan.length}{t("개, 예상")}{" "}{plan.length * minutes}{t("분")}{" "}</p>
        <div className="overview-items">
          {plan.map((e, i) => (
            <button
              className="plan-step"
              key={e.key}
              onClick={() => openEvent(e.key)}
            >
              <span className="plan-number">{i + 1}</span>
              <span className="plan-item-copy">
                <strong title={e.title}>{e.title}</strong>
                <small>{e.course_name}</small>
              </span>
            </button>
          ))}
        </div>
        {!plan.length && (
          <p>
            {budget < minutes &&
            studyPlan(data.events, now, minutes, minutes).length
              ? t("학습 시간 부족")
              : t("일정 없음")}
          </p>
        )}
      </article>
      <article className="overview-card">
        <h2>{t("마감 밀집 경고")}</h2>
        {crowded.length ? (
          crowded.map(([day, items]) => (
            <details key={day}>
              <summary>
                {day}, {items.length}{t("개")}{" "}</summary>
              <div className="overview-items">
                {items.map((e) => (
                  <button
                    className="plan-warning-item"
                    key={e.key}
                    onClick={() => openEvent(e.key)}
                  >
                    <strong title={e.title}>{e.title}</strong>
                  </button>
                ))}
              </div>
            </details>
          ))
        ) : (
          <p className="muted">{t("밀집 마감 없음")}</p>
        )}
      </article>
    </div>
  );
}
