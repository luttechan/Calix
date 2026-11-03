import { memo, useEffect, useRef, useState } from "react";
import { Check, RefreshCw, TriangleAlert, X } from "lucide-react";
import { playSyncCue } from "./syncCue";
import { rpc, subscribe } from "./bridge";
import { syncNoticeState, type SyncNoticeState } from "./syncNoticeState";

export const SyncNotice = memo(function SyncNotice({
  sound,
  volume,
}: {
  sound: boolean;
  volume: number;
}) {
  const [state, setState] = useState<SyncNoticeState | null>(null),
    [visible, setVisible] = useState(false),
    [leaving, setLeaving] = useState(false);
  const [details, setDetails] = useState(false);
  const cue = useRef<(() => void) | null>(null);
  const latest = useRef<SyncNoticeState | null>(null),
    soundOptions = useRef({ sound, volume });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    exitTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  soundOptions.current = { sound, volume };
  const dismiss = () => {
    if (timer.current) clearTimeout(timer.current);
    setLeaving(true);
    exitTimer.current = setTimeout(() => {
      setVisible(false);
    }, 180);
  };
  useEffect(
    () =>
      subscribe((event) => {
        if (
          event.event === "sync-started" ||
          (event.event === "authentication" && event.loggedIn === false)
        ) {
          cue.current?.();
          cue.current = null;
        }
        if (event.event === "sync-complete") {
          cue.current?.();
          const token = event.reminderToken;
          cue.current = playSyncCue(
            soundOptions.current.sound,
            soundOptions.current.volume,
            () => {
              if (typeof token === "string")
                void rpc("reminders.sync-ready", { token }).catch(() => {});
            },
          );
        }
        const previous = latest.current,
          next = syncNoticeState(previous, event);
        if (next === previous) return;
        latest.current = next;
        setState(next);
        if (event.event === "sync-started") {
          if (exitTimer.current) clearTimeout(exitTimer.current);
          setDetails(false);
          setLeaving(false);
          setVisible(true);
        } else if (!previous) {
          setVisible(true);
          setLeaving(false);
        }
        if (timer.current) clearTimeout(timer.current);
        if (next && next.phase !== "running") {
          if (exitTimer.current) clearTimeout(exitTimer.current);
          setVisible(true);
          setLeaving(false);
          timer.current = setTimeout(
            dismiss,
            next.phase === "error" || next.phase === "warning" ? 10000 : 6000,
          );
        }
      }),
    [],
  );
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
      if (exitTimer.current) clearTimeout(exitTimer.current);
      cue.current?.();
    },
    [],
  );
  if (!visible || !state) return null;
  const running = state.phase === "running",
    failed = state.phase === "error" || state.phase === "warning";
  const progress = state.total
    ? Math.round((state.current / state.total) * 100)
    : null;
  const seconds = state.remainingSeconds;
  const estimate = seconds === null
    ? state.total > 0 && state.current === state.total ? "마무리 중" : "예상 시간 계산 중"
    : seconds < 60
      ? `약 ${seconds}초 남음`
      : `약 ${Math.floor(seconds / 60)}분 ${seconds % 60}초 남음`;
  const title = running
    ? "동기화 중"
    : state.phase === "success"
      ? "동기화 완료"
      : state.phase === "warning"
        ? "동기화 일부 완료"
        : state.phase === "cancelled"
          ? "동기화 중단"
          : "동기화 실패";
  return (
    <aside
      className={`sync-notice ${state.phase} ${leaving ? "leaving" : ""}`}
      aria-label="동기화 알림"
    >
      <header>
        <span className="sync-notice-icon">
          {running ? (
            <RefreshCw size={20} />
          ) : failed ? (
            <TriangleAlert size={20} />
          ) : (
            <Check size={20} />
          )}
        </span>
        <div role={state.phase === "error" ? "alert" : "status"}>
          <strong>{title}</strong>
          {state.message !== title && <p>{state.message}</p>}
        </div>
        <button
          className="icon-button"
          aria-label="동기화 알림 닫기"
          onClick={dismiss}
        >
          <X size={16} />
        </button>
      </header>
      {running ? (
        <>
          <div
            className={`sync-notice-progress ${progress === null ? "indeterminate" : ""}`}
            role="progressbar"
            aria-label="강의 확인 진행률"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress ?? undefined}
          >
            <span
              style={
                progress === null
                  ? undefined
                  : { transform: `scaleX(${progress / 100})` }
              }
            />
          </div>
          <footer>
            <span>
              {state.total
                ? `${state.current} / ${state.total}개 강의`
                : "학교 응답을 기다리는 중"}
            </span>
            <span>{estimate}</span>
          </footer>
        </>
      ) : (
        state.phase !== "cancelled" && (
          <div className="sync-notice-counts">
            {state.phase !== "error" && (
              <>
                <span>
                  신규 강의 <b>{state.stats.new_courses || 0}</b>
                </span>
                <span>
                  새 일정 <b>{state.stats.new || 0}</b>
                </span>
                <span>
                  변경 <b>{state.stats.updated || 0}</b>
                </span>
                {Boolean(state.stats.reused_courses) && (
                  <span>
                    재사용 <b>{state.stats.reused_courses}</b>
                  </span>
                )}
              </>
            )}
            {state.warnings.length > 0 && (
              <button
                onClick={() => {
                  setDetails(!details);
                  if (timer.current) clearTimeout(timer.current);
                  if (details) timer.current = setTimeout(dismiss, 6000);
                }}
                aria-expanded={details}
              >
                확인 {state.warnings.length}건
              </button>
            )}
          </div>
        )
      )}
      {details && (
        <ul className="sync-notice-errors">
          {state.warnings.map((text, index) => (
            <li key={index}>{text}</li>
          ))}
        </ul>
      )}
    </aside>
  );
});
