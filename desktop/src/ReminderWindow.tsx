import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { ArrowRight, Bell, BellRing, ClipboardList, Play, Timer, Volume2, X } from "lucide-react";
import type { ReminderPayload } from "./types";
import { acceptReminder } from "./reminderState";
import { locale, setLanguage, t, useLanguage } from "./i18n";
import { dragWindow } from "./windowDrag";
function useSound(sound: string, volume: number, signal: unknown) {
  const [blocked, setBlocked] = useState(false);
  const current = useRef<HTMLAudioElement | null>(null);
  const play = () => {
    const audio = current.current;
    if (audio) {
      audio.currentTime = 0;
      void audio
        .play()
        .then(() => setBlocked(false))
        .catch(() => setBlocked(true));
    }
  };
  useEffect(() => {
    setBlocked(false);
    if (!sound) return;
    const audio = new Audio(`/assets/alarm/${sound}.mp3`);
    audio.volume = volume;
    current.current = audio;
    let active = true;
    void audio.play().catch(() => {
      if (active) setBlocked(true);
    });
    return () => {
      active = false;
      audio.pause();
      audio.src = "";
      audio.load();
      if (current.current === audio) current.current = null;
    };
  }, [sound, volume, signal]);
  return { blocked, play };
}

function countdown(due: number, now: number) {
  if (due <= now) return t("기한 경과");
  if (due - now < 60000) return t("1분 미만");
  const minutes = Math.ceil((due - now) / 60000);
  const hours = Math.floor(minutes / 60);
  if (hours >= 24) return t("{0}일 {1}시간 남음", [Math.floor(hours / 24), hours % 24]);
  if (!hours) return t("{0}분 남음", [minutes]);
  if (minutes % 60 === 0) return t("{0}시간 남음", [hours]);
  return t("{0}시간 {1}분 남음", [hours, minutes % 60]);
}

export function ReminderCard({
  payload,
  onClose,
  onOpen,
}: {
  payload: ReminderPayload;
  onClose: () => void;
  onOpen: (key: string) => void;
}) {
  useLanguage();
  const { blocked, play } = useSound(payload.sound, payload.volume, payload);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!payload.urgent) return;
    setNow(Date.now());
    const interval = window.setInterval(() => setNow(Date.now()), 15000);
    return () => window.clearInterval(interval);
  }, [payload]);
  const earliest = payload.urgent
    ? Math.min(...payload.events
      .filter((event) => event.urgent !== false)
      .map((event) => Date.parse(event.due_at ?? ""))
      .filter(Number.isFinite))
    : Infinity;
  const time = new Intl.DateTimeFormat(locale(), {
    timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const day = new Intl.DateTimeFormat(locale(), { timeZone: "Asia/Seoul", month: "short", day: "numeric" });
  const count = new Intl.NumberFormat(locale()).format(payload.total);
  return (
    <article className={`reminder-card ${payload.urgent ? "urgent" : ""}`}>
      <header className="reminder-brand" onMouseDown={dragWindow}>
        <span>
          <img src="/assets/icons/calix.svg" alt="" />
          Calix
        </span>
        <button
          className="icon-button"
          aria-label={t("알림 닫기")}
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>
      <div className="reminder-intro">
        {payload.urgent ? <BellRing size={20} aria-hidden="true" /> : <Bell size={20} aria-hidden="true" />}
        <h1>{t(payload.urgent ? "긴급 마감" : payload.due_today ? "오늘 마감" : "다가오는 마감")}</h1>
        <span className="reminder-count" aria-label={t("총 {0}건", [count])}>{count}</span>
      </div>
      {Number.isFinite(earliest) && (
        <div className="reminder-countdown">
          <Timer size={17} aria-hidden="true" />
          <span>{t("가장 가까운 마감")}</span>
          <strong>{countdown(earliest, now)}</strong>
        </div>
      )}
      <div className="reminder-events" role="region" aria-label={t("마감 예정 일정")} tabIndex={0}>
        {payload.events.map((event) => {
          const due = new Date(event.due_at ?? "");
          const valid = Number.isFinite(due.getTime());
          const assignment = event.kind === "assignment";
          return (
          <button key={event.key} onClick={() => onOpen(event.key)} data-urgent={event.urgent || undefined}>
            <span className={`reminder-type ${event.kind}`} aria-label={t(assignment ? "과제" : "영상")} title={t(assignment ? "과제" : "영상")}>
              {assignment ? <ClipboardList size={17} aria-hidden="true" /> : <Play size={17} aria-hidden="true" />}
            </span>
            <span className="reminder-event-name">
              <strong title={event.title}>{event.title}</strong>
              <small title={event.course_name}>{event.course_name}</small>
            </span>
            {valid && <time dateTime={event.due_at!}><span>{day.format(due)}</span><strong>{time.format(due)}</strong></time>}
          </button>
        );})}
        {payload.total > payload.events.length && (
          <p className="reminder-list-more">
            {t("그 외 {0}건", [payload.total - payload.events.length])}
          </p>
        )}
      </div>
      <footer>
        {blocked && (
          <button className="quiet" onClick={play}>
            <Volume2 size={16} />
            {t("소리 재생")}
          </button>
        )}
        <span />
        <button className="primary" onClick={() => onOpen("")}>
          {t("일정 보기")}
          <ArrowRight size={15} aria-hidden="true" />
        </button>
      </footer>
    </article>
  );
}
export function ReminderWindow() {
  const [state, setState] = useState<{
    revision: number;
    payload: ReminderPayload | null;
  }>({ revision: -1, payload: null });
  const latest = useRef(-1);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let stop: (() => void) | undefined;
    const receive = (value: {
      revision: number;
      payload: ReminderPayload | null;
    }) => {
      if (active)
        setState((current) => {
          const next = acceptReminder(current, value);
          latest.current = next.revision;
          return next;
        });
    };
    void (async () => {
      const clean = await listen<{
        revision: number;
        payload: ReminderPayload | null;
      }>("reminder:state", (event) => receive(event.payload));
      if (!active) {
        clean();
        return;
      }
      stop = clean;
      receive(await invoke("reminder_payload"));
    })().catch((e) => {
      if (active) setError(String(e));
    });
    return () => {
      active = false;
      stop?.();
    };
  }, []);
  useEffect(() => {
    if (state.payload) {
      setLanguage(state.payload.language);
      document.documentElement.dataset.theme = state.payload.theme;
      document.documentElement.dataset.glass = String(state.payload.glass);
    }
  }, [state.payload]);
  const close = () =>
    void invoke("reminder_close", { revision: latest.current }).catch((e) =>
      setError(String(e)),
    );
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  return state.payload ? (
    <ReminderCard
      payload={state.payload}
      onClose={close}
      onOpen={(key) =>
        void invoke("reminder_open_event", {
          key,
          revision: state.revision,
        }).catch((e) => setError(String(e)))
      }
    />
  ) : (
    <div className="empty">{error || ""}</div>
  );
}
