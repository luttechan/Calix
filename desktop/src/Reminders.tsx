import { t, useLanguage } from "./i18n";
import { NumberField } from "./NumberField";
import { useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { Bell, BellRing, Volume2 } from "lucide-react";
import { useCalix } from "./App";
import { alarmNames } from "./alarmNames";
import { defaultSyncTrack, syncCuePath } from "./syncCue";
import type { ReminderSettings } from "./types";

export function ReminderSettingsPanel({ active = true }: { active?: boolean }) {
  useLanguage();
  const { data, mutate, notify } = useCalix();
  const [form, setForm] = useState<ReminderSettings>(
    data.preferences.reminders,
  );
  const [saving, setSaving] = useState(false),
    [catalog, setCatalog] = useState<{ tracks: number[]; critical: boolean }>({
      tracks: [],
      critical: false,
    });
  const [syncTracks, setSyncTracks] = useState<number[]>([1]);
  const syncTrack = syncTracks.includes(Number(form.sync_track)) ? form.sync_track! : defaultSyncTrack;
  const [playing, setPlaying] = useState("");
  const audio = useRef<HTMLAudioElement | null>(null);
  const releasePreview = () => {
    const current = audio.current;
    audio.current = null;
    if (current) {
      current.onended = null;
      current.pause();
      current.removeAttribute("src");
      current.load();
    }
  };
  useEffect(() => {
    releasePreview();
    setPlaying("");
  }, [form.enabled, form.sound, form.track, syncTrack, form.volume, active]);
  const saved = JSON.stringify(data.preferences.reminders);
  const [section, setSection] = useState<"rules" | "sound">("rules");
  const urgentUnit = form.urgent_unit ?? (form.urgent_minutes % 60 ? "minutes" : "hours");
  const hourUnit = urgentUnit === "hours";
  const [generalCustom, setGeneralCustom] = useState(
    ![0, 1, 3, 7].includes(form.general_days),
  );
  useEffect(() => {
    const value = JSON.parse(saved) as ReminderSettings;
    setForm(value);
    setGeneralCustom(![0, 1, 3, 7].includes(value.general_days));
  }, [saved]);
  useEffect(() => {
    releasePreview();
    setPlaying("");
  }, [section]);
  useEffect(() => {
    let active = true;
    void fetch("/assets/alarm/catalog.json")
      .then((r) => r.json())
      .then((value) => {
        if (active) setCatalog(value);
      })
      .catch(() => {});
    void fetch("/assets/sound/catalog.json")
      .then((r) => r.json())
      .then((value) => {
        if (active && Array.isArray(value)) setSyncTracks([1, ...value.filter((n) => Number.isInteger(n) && n >= 2 && n <= 10)]);
      })
      .catch(() => {});
    return () => {
      active = false;
      releasePreview();
    };
  }, []);
  const change = <K extends keyof ReminderSettings>(
    key: K,
    value: ReminderSettings[K],
  ) => setForm((previous) => ({ ...previous, [key]: value }));
  const testSound = (path: string) => {
    releasePreview();
    if (playing === path) {
      setPlaying("");
      return;
    }
    setPlaying(path);
    const next = new Audio(path);
    next.volume = form.volume;
    audio.current = next;
    next.onended = () => {
      if (audio.current !== next) return;
      releasePreview();
      setPlaying("");
    };
    void next.play().catch(() => {
        if (audio.current !== next) return;
        releasePreview();
        setPlaying("");
        notify("음원을 재생하지 못했습니다.", true);
      });
  };
  const normalPath = `/assets/alarm/${form.track}.mp3`;
  const urgentPath = "/assets/alarm/crit.mp3";
  const syncPath = syncCuePath(syncTrack);
  const dirty = JSON.stringify(form) !== saved;
  return (
    <section className="glass settings-panel reminder-settings">
      <div className="alarm-panel-heading">
        <div className="settings-heading">
          <Bell aria-hidden="true" />
          <h2>{t("알림과 소리")}</h2>
        </div>
        <label className="alarm-enable">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(e) => change("enabled", e.target.checked)}
          />{t("알림 켜기")}{" "}</label>
      </div>
      <div className="alarm-tabs" role="tablist" aria-label={t("알림 설정 구분")}>
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
            {t(label)}
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
              <h3>{t("표시 시점")}</h3>
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
                    <span>{t(label)}</span>
                  </label>
                ))}
              </div>
            </section>
            <section className="alarm-group">
              <h3>{t("알림 대상")}</h3>
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
                    <span>{t(label)}</span>
                  </label>
                ))}
              </div>
            </section>
            <section className="alarm-group">
              <h3>{t("마감 알림")}</h3>
              <div className="alarm-deadline-grid">
                <div className="alarm-deadline alarm-deadline-urgent">
                  <label className="alarm-choice alarm-rule-title">
                    <input
                      type="checkbox"
                      checked={form.urgent}
                      onChange={(e) => change("urgent", e.target.checked)}
                    />
                    <strong>{t("긴급 마감")}</strong>
                    <BellRing size={16} aria-hidden="true" />
                  </label>
                  <div className="alarm-urgent-interval">
                    <NumberField
                      key={urgentUnit}
                      aria-label={t("긴급 알림 시간")}
                      min={1}
                      max={hourUnit ? 168 : 10080}
                      step={1}
                      required
                      disabled={!form.urgent}
                      value={hourUnit ? form.urgent_minutes / 60 : form.urgent_minutes}
                      onValueChange={(value) => {
                        if (!Number.isInteger(value) || value < 1 || value > (hourUnit ? 168 : 10080)) return;
                        setForm((previous) => ({
                          ...previous,
                          urgent_unit: urgentUnit,
                          urgent_minutes: value * (hourUnit ? 60 : 1),
                        }));
                      }}
                    />
                    <select
                      aria-label={t("시간 단위")}
                      disabled={!form.urgent}
                      value={urgentUnit}
                      onChange={(event) => {
                        const unit = event.target.value === "hours" ? "hours" : "minutes";
                        setForm((previous) => ({
                          ...previous,
                          urgent_unit: unit,
                          urgent_minutes: unit === "hours"
                            ? Math.max(1, Math.round(previous.urgent_minutes / 60)) * 60
                            : previous.urgent_minutes,
                        }));
                      }}
                    >
                      <option value="minutes">{t("분 전")}</option>
                      <option value="hours">{t("시간 전")}</option>
                    </select>
                  </div>
                </div>
                <div className="alarm-deadline">
                  <label className="alarm-choice alarm-rule-title">
                    <input
                      type="checkbox"
                      checked={form.general}
                      onChange={(e) => change("general", e.target.checked)}
                    />
                    <strong>{t("일반 REMIND")}</strong>
                  </label>
                  <select
                    aria-label={t("일반 알림 시간")}
                    disabled={!form.general}
                    value={generalCustom ? "custom" : String(form.general_days)}
                    onChange={(e) => {
                      const custom = e.target.value === "custom";
                      setGeneralCustom(custom);
                      if (!custom)
                        change("general_days", Number(e.target.value));
                    }}
                  >
                    <option value="0">{t("오늘 마감")}</option>
                    <option value="1">{t("하루 전")}</option>
                    <option value="3">{t("3일 전")}</option>
                    <option value="7">{t("7일 전")}</option>
                    <option value="custom">{t("직접 입력")}</option>
                  </select>
                  {generalCustom && (
                    <div className="alarm-number">
                      <NumberField
                        aria-label={t("일반 알림 일")}

                        min={0}
                        max={365}
                        required
                        step={1}
                        disabled={!form.general}
                        value={form.general_days}
                        onValueChange={value => change("general_days", value)}
                      />
                      <span>{t("일 전")}</span>
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
              <h3>{t("알림 소리")}</h3>
              <label className="alarm-choice">
                <input
                  type="checkbox"
                  checked={form.sound}
                  onChange={(e) => change("sound", e.target.checked)}
                />{t("소리 켜기")}{" "}</label>
            </section>
            <div className="alarm-track-row">
              <div>
                <strong>{t("일반 알람")}</strong>
                <select
                  aria-label={t("일반 알람 음원")}
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
                aria-label={t("일반 알람 미리 듣기")}
                disabled={!form.sound || !catalog.tracks.length}
                onClick={() => testSound(normalPath)}
              >
                <Volume2 size={16} />
                {playing === normalPath ? t("중지") : t("미리 듣기")}
              </button>
            </div>
            <div className="alarm-track-row">
              <div>
                <strong>{t("긴급 알람")}</strong>
                <span className="alarm-file">{alarmNames.crit}</span>
              </div>
              <button
                type="button"
                aria-label={t("긴급 알람 미리 듣기")}
                disabled={!form.sound || !catalog.critical}
                onClick={() => testSound(urgentPath)}
              >
                <Volume2 size={16} />
                {playing === urgentPath ? t("중지") : t("미리 듣기")}
              </button>
            </div>
            <div className="alarm-track-row">
              <div>
                <strong>{t("동기화 완료음")}</strong>
                <select aria-label={t("동기화 완료음")} value={syncTrack} disabled={!form.sound} onChange={(event) => change("sync_track", event.target.value)}>
                  {syncTracks.map((track) => <option value={String(track)} key={track}>Notification {track}</option>)}
                </select>
              </div>
              <button type="button" aria-label={t("동기화 완료음 미리 듣기")} disabled={!form.sound} onClick={() => testSound(syncPath)}>
                <Volume2 size={16} /> {playing === syncPath ? t("중지") : t("미리 듣기")}
              </button>
            </div>
            <label className="alarm-volume">{t("음량")}{" "}<output>{Math.round(form.volume * 100)}%</output>
              <input
                aria-label={t("알람 음량")}
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
            {dirty ? t("저장하지 않은 변경 사항") : ""}
          </span>
          <button className="primary" disabled={saving}>
            {saving ? t("저장 중") : t("알림 설정 저장")}
          </button>
        </div>
      </form>
    </section>
  );
}
