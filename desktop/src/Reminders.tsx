import { useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { Bell, BellRing, Check, Volume2, X, ArrowUpRight } from "lucide-react";
import { useCalix } from "./App";
import { dueText } from "./dates";
import { alarmNames } from "./alarmNames";
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
export function ReminderSettingsPanel({ active = true }: { active?: boolean }) {
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
  const saved = JSON.stringify(data.preferences.reminders);
  const [section, setSection] = useState<"rules" | "sound">("rules");
  const [urgentCustom, setUrgentCustom] = useState(
    ![10, 60, 180, 300].includes(form.urgent_minutes),
  );
  const [generalCustom, setGeneralCustom] = useState(
    ![0, 1, 3, 7].includes(form.general_days),
  );
  useEffect(() => {
    const value = JSON.parse(saved) as ReminderSettings;
    setForm(value);
    setUrgentCustom(![10, 60, 180, 300].includes(value.urgent_minutes));
    setGeneralCustom(![0, 1, 3, 7].includes(value.general_days));
  }, [saved]);
  useEffect(() => {
    audio.current?.pause();
    if (audio.current) {
      audio.current.src = "";
      audio.current.load();
    }
    audio.current = null;
    setPlaying(false);
  }, [active, section]);
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
  const testSound = (critical: boolean) => {
    audio.current?.pause();
    if (playing && testCritical === critical) {
      setPlaying(false);
      return;
    }
    setTestCritical(critical);
    const track = critical ? "crit" : form.track;
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
        if (audio.current !== next) return;
        setPlaying(false);
        notify("음원을 재생하지 못했습니다.");
      });
  };
  const dirty = JSON.stringify(form) !== saved;
  return (
    <section className="glass settings-panel reminder-settings">
      <div className="alarm-panel-heading">
        <div>
          <h2>알림과 소리</h2>
          <p>Calix 실행 중에 알립니다.</p>
        </div>
        <label className="alarm-enable">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(e) => change("enabled", e.target.checked)}
          />
          알림 켜기
        </label>
      </div>
      <div className="alarm-tabs" role="tablist" aria-label="알림 설정 구분">
        {(
          [
            ["rules", "알림 조건"],
            ["sound", "소리"],
          ] as const
        ).map(([id, label]) => (
          <button
            type="button"
            key={id}
            role="tab"
            aria-selected={section === id}
            aria-controls={`alarm-pane-${id}`}
            id={`alarm-tab-${id}`}
            onClick={() => setSection(id)}
          >
            {label}
          </button>
        ))}
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
        <fieldset className="alarm-fields" disabled={!form.enabled}>
          <div
            role="tabpanel"
            id="alarm-pane-rules"
            aria-labelledby="alarm-tab-rules"
            hidden={section !== "rules"}
          >
            <section className="alarm-group">
              <h3>표시 시점</h3>
              <div className="alarm-choice-grid">
                {(
                  [
                    ["startup", "실행할 때마다 켜기"],
                    ["sync", "동기화할 때마다 켜기"],
                  ] as const
                ).map(([key, label]) => (
                  <label className="alarm-choice" key={key}>
                    <input
                      type="checkbox"
                      checked={form[key]}
                      onChange={(e) => change(key, e.target.checked)}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </section>
            <section className="alarm-group">
              <h3>알림 대상</h3>
              <div className="alarm-choice-grid">
                {(
                  [
                    ["assignments", "과제"],
                    ["videos", "영상"],
                  ] as const
                ).map(([key, label]) => (
                  <label className="alarm-choice" key={key}>
                    <input
                      type="checkbox"
                      checked={form[key]}
                      onChange={(e) => change(key, e.target.checked)}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </section>
            <section className="alarm-group">
              <h3>마감 알림</h3>
              <div className="alarm-deadline-grid">
                <div className="alarm-deadline">
                  <label className="alarm-choice alarm-rule-title">
                    <input
                      type="checkbox"
                      checked={form.urgent}
                      onChange={(e) => change("urgent", e.target.checked)}
                    />
                    <strong>긴급 REMIND</strong>
                  </label>
                  <select
                    aria-label="긴급 알림 시간"
                    disabled={!form.urgent}
                    value={
                      urgentCustom ? "custom" : String(form.urgent_minutes)
                    }
                    onChange={(e) => {
                      const custom = e.target.value === "custom";
                      setUrgentCustom(custom);
                      if (!custom)
                        change("urgent_minutes", Number(e.target.value));
                    }}
                  >
                    <option value="10">10분 전</option>
                    <option value="60">1시간 전</option>
                    <option value="180">3시간 전</option>
                    <option value="300">5시간 전</option>
                    <option value="custom">직접 입력</option>
                  </select>
                  {urgentCustom && (
                    <div className="alarm-number">
                      <input
                        aria-label="긴급 알림 분"
                        type="number"
                        min={1}
                        max={10080}
                        required
                        step={1}
                        disabled={!form.urgent}
                        value={form.urgent_minutes}
                        onChange={(e) =>
                          change("urgent_minutes", Number(e.target.value))
                        }
                      />
                      <span>분 전</span>
                    </div>
                  )}
                  <small>긴급 음원: {alarmNames.crit}</small>
                </div>
                <div className="alarm-deadline">
                  <label className="alarm-choice alarm-rule-title">
                    <input
                      type="checkbox"
                      checked={form.general}
                      onChange={(e) => change("general", e.target.checked)}
                    />
                    <strong>일반 REMIND</strong>
                  </label>
                  <select
                    aria-label="일반 알림 시간"
                    disabled={!form.general}
                    value={generalCustom ? "custom" : String(form.general_days)}
                    onChange={(e) => {
                      const custom = e.target.value === "custom";
                      setGeneralCustom(custom);
                      if (!custom)
                        change("general_days", Number(e.target.value));
                    }}
                  >
                    <option value="0">오늘 마감</option>
                    <option value="1">하루 전</option>
                    <option value="3">3일 전</option>
                    <option value="7">7일 전</option>
                    <option value="custom">직접 입력</option>
                  </select>
                  {generalCustom && (
                    <div className="alarm-number">
                      <input
                        aria-label="일반 알림 일"
                        type="number"
                        min={0}
                        max={365}
                        required
                        step={1}
                        disabled={!form.general}
                        value={form.general_days}
                        onChange={(e) =>
                          change("general_days", Number(e.target.value))
                        }
                      />
                      <span>일 전</span>
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>
          <div
            role="tabpanel"
            id="alarm-pane-sound"
            aria-labelledby="alarm-tab-sound"
            hidden={section !== "sound"}
          >
            <section className="alarm-group alarm-sound-header">
              <h3>알림 소리</h3>
              <label className="alarm-choice">
                <input
                  type="checkbox"
                  checked={form.sound}
                  onChange={(e) => change("sound", e.target.checked)}
                />
                소리 켜기
              </label>
            </section>
            <div className="alarm-track-row">
              <div>
                <strong>일반 알람</strong>
                <select
                  aria-label="일반 알람 음원"
                  disabled={!form.sound}
                  value={form.track}
                  onChange={(e) => change("track", e.target.value)}
                >
                  {catalog.tracks.map((n) => (
                    <option key={n} value={String(n)}>
                      {alarmNames[String(n)] || `Alarm ${n}`}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                aria-label="일반 알람 미리 듣기"
                disabled={!form.sound || !catalog.tracks.length}
                onClick={() => testSound(false)}
              >
                <Volume2 size={16} />
                {playing && !testCritical ? "중지" : "미리 듣기"}
              </button>
            </div>
            <div className="alarm-track-row">
              <div>
                <strong>긴급 알람</strong>
                <span className="alarm-file">{alarmNames.crit}</span>
              </div>
              <button
                type="button"
                aria-label="긴급 알람 미리 듣기"
                disabled={!form.sound || !catalog.critical}
                onClick={() => testSound(true)}
              >
                <Volume2 size={16} />
                {playing && testCritical ? "중지" : "미리 듣기"}
              </button>
            </div>
            <label className="alarm-volume">
              음량 <output>{Math.round(form.volume * 100)}%</output>
              <input
                aria-label="알람 음량"
                type="range"
                min={0}
                max={1}
                step={0.05}
                disabled={!form.sound}
                value={form.volume}
                onChange={(e) => change("volume", Number(e.target.value))}
              />
            </label>
          </div>
        </fieldset>
        <div className="alarm-save">
          <span aria-live="polite">
            {dirty ? "저장하지 않은 변경 사항" : ""}
          </span>
          <button className="primary" disabled={saving}>
            {saving ? "저장 중" : "알림 설정 저장"}
          </button>
        </div>
      </form>
    </section>
  );
}
