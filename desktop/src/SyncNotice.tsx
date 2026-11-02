import { memo, useEffect, useRef, useState } from "react";
import { Check, RefreshCw, TriangleAlert, X } from "lucide-react";
import { subscribe } from "./bridge";
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
  const reminderSoundAt = useRef(0);
  const latest = useRef<SyncNoticeState | null>(null),
    soundOptions = useRef({ sound, volume });
  const audio = useRef<HTMLAudioElement | null>(null),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    exitTimer = useRef<ReturnType<typeof setTimeout> | null>(null),
    soundTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  soundOptions.current = { sound, volume };
  const release = () => {
    if (soundTimer.current) clearTimeout(soundTimer.current);
    if (audio.current) {
      const old = audio.current;
      audio.current = null;
      old.onended = null;
      old.onerror = null;
      old.pause();
      old.removeAttribute("src");
      old.load();
    }
  };
  const dismiss = () => {
    if (timer.current) clearTimeout(timer.current);
    setLeaving(true);
    exitTimer.current = setTimeout(() => {
      setVisible(false);
      release();
    }, 180);
  };
  useEffect(
    () =>
      subscribe((event) => {
        if (event.event === "reminder") {
          const payload = event.payload as
            { sound?: string; volume?: number } | undefined;
          if (payload?.sound && Number(payload.volume) > 0) {
            reminderSoundAt.current = Date.now();
            release();
          }
          return;
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
          release();
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
          release();
          if (
            next.phase !== "cancelled" &&
            soundOptions.current.sound &&
            Date.now() - reminderSoundAt.current > 3000
          ) {
            const player = new Audio("/assets/sound/notify.mp3");
            audio.current = player;
            player.volume = Math.min(
              1,
              Math.max(0, soundOptions.current.volume),
            );
            player.onended = release;
            player.onerror = release;
            void player.play().catch(() => {
              if (audio.current === player) release();
            });
            soundTimer.current = setTimeout(release, 15000);
          }
        }
      }),
    [],
  );
  useEffect(() => {
    if (!sound) release();
  }, [sound]);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
      if (exitTimer.current) clearTimeout(exitTimer.current);
      release();
    },
    [],
  );
  if (!visible || !state) return null;
  const running = state.phase === "running",
    failed = state.phase === "error" || state.phase === "warning";
  const progress = state.total
    ? Math.round((state.current / state.total) * 100)
    : null;
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
            {progress !== null && <span>{progress}%</span>}
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
