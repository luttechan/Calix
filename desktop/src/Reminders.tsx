import { useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { Bell, BellRing, Check, Volume2, X, ArrowUpRight } from "lucide-react";
import { useCalix } from "./App";
import { dueText } from "./dates";
import type { EventItem, ReminderSettings, ReminderPayload } from "./types";

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
          Calix
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
        <span className="reminder-bell">
          {payload.urgent ? <BellRing size={28} /> : <Bell size={28} />}
        </span>
        <p className="eyebrow">{payload.urgent ? "긴급 REMIND" : "REMIND"}</p>
        <h1>{payload.title}</h1>
        <p>{payload.message}</p>
      </div>
      <div className="reminder-events">
        {payload.events.map((event) => (
          <button key={event.key} onClick={() => onOpen(event.key)}>
            <span className={`reminder-type ${event.kind}`}>
              {event.kind === "assignment" ? "과제" : "영상"}
            </span>
            <span>
              <small>{event.course_name}</small>
              <strong>{event.title}</strong>
              <small>{dueText(event.due_at)}</small>
            </span>
            <ArrowUpRight size={16} />
          </button>
        ))}
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
  const [payload, setPayload] = useState<ReminderPayload | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let stop: (() => void) | undefined;
    void listen<ReminderPayload>("reminder:updated", (event) => {
      if (active) setPayload(event.payload);
    }).then((clean) => {
      if (active) stop = clean;
      else clean();
    });
    void invoke<ReminderPayload>("reminder_payload")
      .then((value) => {
        if (active) setPayload(value);
      })
      .catch((e) => {
        if (active) setError(String(e));
      });
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") void invoke("reminder_close");
    };
    window.addEventListener("keydown", key);
    return () => {
      active = false;
      stop?.();
      window.removeEventListener("keydown", key);
    };
  }, []);
  useEffect(() => {
    if (payload) {
      document.documentElement.dataset.theme = payload.theme;
      document.documentElement.dataset.glass = String(payload.glass);
    }
  }, [payload]);
  return payload ? (
    <ReminderCard
      payload={payload}
      onClose={() => void invoke("reminder_close")}
      onOpen={(key) => void invoke("reminder_open_event", { key })}
    />
  ) : (
    <div className="empty">{error || "알림을 준비하고 있어요."}</div>
  );
}
export function ReminderSettingsPanel() {
  const { data, mutate, notify } = useCalix();
  const [form, setForm] = useState<ReminderSettings>(
    data.preferences.reminders,
  );
  const [saving, setSaving] = useState(false),
    [catalog, setCatalog] = useState<{ tracks: number[]; critical: boolean }>({
      tracks: [],
      critical: false,
    });
  const [playing, setPlaying] = useState(false),
    [testCritical, setTestCritical] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => {
    audio.current?.pause();
    if (audio.current) {
      audio.current.src = "";
      audio.current.load();
    }
    audio.current = null;
    setPlaying(false);
  }, [form.enabled, form.sound, form.track, form.volume]);
  useEffect(() => {
    setForm(data.preferences.reminders);
  }, [data.preferences.reminders]);
  useEffect(() => {
    let active = true;
    void fetch("/assets/alarm/catalog.json")
      .then((r) => r.json())
      .then((value) => {
        if (active) setCatalog(value);
      })
      .catch(() => {});
    return () => {
      active = false;
      audio.current?.pause();
      if (audio.current) {
        audio.current.src = "";
        audio.current.load();
      }
      audio.current = null;
    };
  }, []);
  const change = <K extends keyof ReminderSettings>(
    key: K,
    value: ReminderSettings[K],
  ) => setForm((previous) => ({ ...previous, [key]: value }));
  const testSound = () => {
    audio.current?.pause();
    if (playing) {
      setPlaying(false);
      return;
    }
    const track = testCritical ? "crit" : form.track;
    const next = new Audio(`/assets/alarm/${track}.mp3`);
    next.volume = form.volume;
    audio.current = next;
    next.onended = () => {
      if (audio.current === next) setPlaying(false);
    };
    void next
      .play()
      .then(() => {
        if (audio.current === next) setPlaying(true);
      })
      .catch(() => {
        setPlaying(false);
        notify("음원을 재생하지 못했습니다.");
      });
  };
  return (
    <section className="glass settings-panel reminder-settings">
      <div className="settings-heading">
        <Bell size={20} />
        <h2>알림과 소리</h2>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (saving) return;
          setSaving(true);
          void mutate("reminders.save", form)
            .then(() => {
              if (!form.enabled && isTauri()) void invoke("reminder_close");
              notify("알림 설정 저장됨");
            })
            .catch(() => {})
            .finally(() => setSaving(false));
        }}
      >
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(e) => change("enabled", e.target.checked)}
          />
          알림 켜기
        </label>
        <fieldset disabled={!form.enabled} className="reminder-options">
          <div className="reminder-checks">
            {(
              [
                ["startup", "실행할 때마다 켜기"],
                ["sync", "동기화할 때마다 켜기"],
                ["assignments", "과제"],
                ["videos", "영상"],
              ] as const
            ).map(([key, label]) => (
              <label className="checkbox-label" key={key}>
                <input
                  type="checkbox"
                  checked={form[key]}
                  onChange={(e) => change(key, e.target.checked)}
                />
                {label}
              </label>
            ))}
          </div>
          <div className="reminder-rule">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.urgent}
                onChange={(e) => change("urgent", e.target.checked)}
              />
              긴급 REMIND
            </label>
            <div className="reminder-time-inputs">
              <select
                aria-label="긴급 알림 시간"
                disabled={!form.urgent}
                value={
                  [10, 60, 180, 300].includes(form.urgent_minutes)
                    ? String(form.urgent_minutes)
                    : "custom"
                }
                onChange={(e) => {
                  if (e.target.value === "custom") change("urgent_minutes", 30);
                  else change("urgent_minutes", Number(e.target.value));
                }}
              >
                <option value="10">10분 전</option>
                <option value="60">1시간 전</option>
                <option value="180">3시간 전</option>
                <option value="300">5시간 전</option>
                <option value="custom">직접 입력</option>
              </select>
              <label>
                <input
                  aria-label="긴급 알림 분"
                  type="number"
                  min={1}
                  max={10080}
                  step={1}
                  required
                  disabled={!form.urgent}
                  value={form.urgent_minutes}
                  onChange={(e) =>
                    change("urgent_minutes", Number(e.target.value))
                  }
                />
                분 전
              </label>
            </div>
            <small>긴급 알람: crit.mp3</small>
          </div>
          <div className="reminder-rule">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.general}
                onChange={(e) => change("general", e.target.checked)}
              />
              일반 REMIND
            </label>
            <div className="reminder-time-inputs">
              <select
                aria-label="일반 알림 시간"
                disabled={!form.general}
                value={
                  [0, 1, 3, 7].includes(form.general_days)
                    ? String(form.general_days)
                    : "custom"
                }
                onChange={(e) =>
                  change(
                    "general_days",
                    e.target.value === "custom" ? 2 : Number(e.target.value),
                  )
                }
              >
                <option value="0">오늘 마감</option>
                <option value="1">하루 전</option>
                <option value="3">3일 전</option>
                <option value="7">7일 전</option>
                <option value="custom">직접 입력</option>
              </select>
              <label>
                <input
                  aria-label="일반 알림 일"
                  type="number"
                  min={0}
                  max={365}
                  step={1}
                  required
                  disabled={!form.general}
                  value={form.general_days}
                  onChange={(e) =>
                    change("general_days", Number(e.target.value))
                  }
                />
                일 전
              </label>
            </div>
          </div>
          <div className="reminder-sound">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.sound}
                onChange={(e) => change("sound", e.target.checked)}
              />
              소리 켜기
            </label>
            <div className="form-grid">
              <label>
                일반 알람
                <select
                  aria-label="일반 알람 음원"
                  disabled={!form.sound}
                  value={form.track}
                  onChange={(e) => change("track", e.target.value)}
                >
                  {catalog.tracks.map((n) => (
                    <option value={String(n)} key={n}>
                      {n}.mp3
                    </option>
                  ))}
                </select>
              </label>
              <label>
                음량
                <input
                  aria-label="알람 음량"
                  disabled={!form.sound}
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={form.volume}
                  onChange={(e) => change("volume", Number(e.target.value))}
                />
              </label>
            </div>
            <div className="reminder-sound-test">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={testCritical}
                  onChange={(e) => {
                    audio.current?.pause();
                    setPlaying(false);
                    setTestCritical(e.target.checked);
                  }}
                />
                긴급 음원 미리 듣기
              </label>
              <button
                type="button"
                disabled={
                  !form.sound ||
                  (!testCritical && !catalog.tracks.length) ||
                  (testCritical && !catalog.critical)
                }
                onClick={testSound}
              >
                <Volume2 size={16} />
                {playing ? "중지" : "미리 듣기"}
              </button>
            </div>
          </div>
        </fieldset>
        <p className="muted">Calix 실행 중에 알립니다.</p>
        <div className="dialog-actions">
          <span />
          <button className="primary" disabled={saving}>
            {saving ? "저장 중" : "알림 설정 저장"}
          </button>
        </div>
      </form>
    </section>
  );
}
