import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { Bell, BellRing, Check, Volume2, X, ArrowUpRight } from "lucide-react";
import { dueText } from "./dates";
import type { ReminderPayload } from "./types";
import { acceptReminder } from "./reminderState";
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
export function ReminderCard({
  payload,
  onClose,
  onOpen,
}: {
  payload: ReminderPayload;
  onClose: () => void;
  onOpen: (key: string) => void;
}) {
  const { blocked, play } = useSound(payload.sound, payload.volume, payload);
  return (
    <article className={`reminder-card ${payload.urgent ? "urgent" : ""}`}>
      <header className="reminder-brand" data-tauri-drag-region>
        <span>
          <img src="/assets/icons/calix.svg" alt="" />
          {`Calix (${__CALIX_VERSION__})`}
        </span>
        <button
          className="icon-button"
          aria-label="알림 닫기"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>
      <div className="reminder-intro">
        <span className="reminder-bell" aria-hidden="true">
          {payload.urgent ? <BellRing size={22} /> : <Bell size={22} />}
        </span>
        <div>
          <p className="eyebrow">{payload.urgent ? "긴급 REMIND" : "REMIND"}</p>
          <h1>{payload.title}</h1>
        </div>
      </div>
      <div className="reminder-list-heading">
        <strong>마감 예정</strong>
        <span>총 {payload.total}건</span>
      </div>
      <div className="reminder-events" role="region" aria-label="마감 예정 일정" tabIndex={0}>
        {payload.events.map((event) => (
          <button key={event.key} onClick={() => onOpen(event.key)}>
            <span className={`reminder-type ${event.kind}`}>
              {event.kind === "assignment" ? "과제" : "영상"}
            </span>
            <span>
              <strong title={event.title}>{event.title}</strong>
              <small>
                <span title={event.course_name}>{event.course_name}</span>
                <time dateTime={event.due_at ?? undefined}>{dueText(event.due_at)}</time>
              </small>
            </span>
            <ArrowUpRight size={16} />
          </button>
        ))}
        {payload.total > payload.events.length && (
          <p className="reminder-list-more">
            나머지 {payload.total - payload.events.length}건은 일정에서 확인할 수 있습니다.
          </p>
        )}
      </div>
      <footer>
        {blocked && (
          <button className="quiet" onClick={play}>
            <Volume2 size={16} />
            소리 재생
          </button>
        )}
        <span />
        <button onClick={() => onOpen("")}>일정 보기</button>
        <button className="primary" onClick={onClose}>
          <Check size={16} />
          확인
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
