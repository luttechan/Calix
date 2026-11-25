import { locale, t, useLanguage } from "./i18n";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { LockKeyhole, ShieldCheck, TriangleAlert, UserRound } from "lucide-react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { Modal, useCalix } from "./App";
import { rpc } from "./bridge";
import { NumberField } from "./NumberField";
import { playLogonCue, stopErrorCue } from "./errorCue";
import type { CredentialMode, SecurityState } from "./types";
import "./security-grades.css";

const credentials = { pin4: "숫자 4자리 PIN", pin6: "숫자 6자리 PIN", password: "6자 이상 비밀번호" } as const;

function CredentialPicker({ mode, onChange, pinSupported }: {
  mode: CredentialMode; onChange: (mode: CredentialMode) => void; pinSupported?: boolean;
}) {
  return <label>{t("잠금 방식")}<select value={mode} onChange={event => onChange(event.target.value as CredentialMode)}>
    {(["pin4", "pin6", "password"] as const).filter(key => pinSupported || key === "password")
      .map(key => <option key={key} value={key}>{t(credentials[key])}</option>)}
  </select></label>;
}

function CredentialInput({ mode, value, onChange, label, required = true, current = false, autoFocus = false }: {
  mode?: CredentialMode | "legacy"; value: string; onChange: (value: string) => void;
  label: string; required?: boolean; current?: boolean; autoFocus?: boolean;
}) {
  const digits = mode === "pin4" ? 4 : mode === "pin6" ? 6 : undefined;
  return <label>{t(label)}<input type="password" autoComplete={current ? "current-password" : "new-password"}
    inputMode={digits ? "numeric" : undefined} pattern={digits ? `[0-9]{${digits}}` : undefined}
    minLength={digits ?? (!current ? 6 : undefined)} maxLength={digits ?? 1024}
    value={value} required={required} autoFocus={autoFocus} onChange={event => onChange(event.target.value)} /></label>;
}

function LockClock() {
  useLanguage();
  const lockTime = new Intl.DateTimeFormat(locale(), { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const lockDate = new Intl.DateTimeFormat(locale(), { month: "long", day: "numeric", weekday: "long" });
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      setNow(new Date());
      timer = setTimeout(tick, 60000 - Date.now() % 60000);
    };
    tick();
    return () => clearTimeout(timer);
  }, []);
  return <div className="lock-clock"><time dateTime={now.toISOString()}>{lockTime.format(now)}</time><span>{lockDate.format(now)}</span></div>;
}

function LockedResetDialog({ onClose }: { onClose: () => void }) {
  useLanguage();
  const { mutate, notify } = useCalix();
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const close = () => { if (!pending) onClose(); };
  return <Modal title={t("데이터 초기화")} className="lock-reset-dialog" onClose={close}>
    <div className="lock-reset-warning" id="lock-reset-warning">
      <TriangleAlert size={19} aria-hidden="true" />
      <div><strong>{t("삭제한 데이터는 복구할 수 없습니다.")}</strong><p>{t("일정, 시간표, 학점, 일기와 비밀번호가 삭제됩니다.")}</p></div>
    </div>
    <label className="lock-reset-field">{t("계속하려면 ‘초기화’를 입력하세요.")}{" "}<input autoFocus aria-label={t("초기화 확인 문구")} aria-describedby="lock-reset-warning" autoComplete="off" maxLength={32} value={confirmation} disabled={pending} onChange={event => setConfirmation(event.target.value)} />
    </label>
    {error && <p role="alert" className="danger">{t(error)}</p>}
    <div className="dialog-actions lock-reset-actions">
      <button type="button" disabled={pending} onClick={close}>{t("취소")}</button>
      <button type="button" className="danger-button" disabled={confirmation !== "초기화" || pending} onClick={() => {
        setPending(true);
        setError("");
        void mutate("data.reset", { confirmation }).then(() => { onClose(); notify("초기화됨"); })
          .catch((reason: Error) => setError(reason.message)).finally(() => setPending(false));
      }}>{pending ? t("초기화 중") : t("초기화")}</button>
    </div>
  </Modal>;
}

export function UnlockView({ scope = "main", onExit }: {
  scope?: "main" | "timetable" | "grades";
  onExit?: () => void;
}) {
  useLanguage();
  const { data, mutate } = useCalix();
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [reset, setReset] = useState(false);
  const [mode, setMode] = useState<CredentialMode>("password");
  const [replacement, setReplacement] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const title = scope === "main" ? "Calix 잠금" : scope === "timetable" ? "시간표 잠금" : "학점 메뉴 잠금";
  const main = scope === "main";
  const migrating = main && data.security?.credential_mode === "legacy";
  const currentMode = data.security?.credential_mode;
  return <>
    <section className={`unlock-view${main ? " startup-unlock" : ""}${migrating ? " startup-migration" : ""}`} aria-labelledby="unlock-title">
      {main ? <><LockClock /><div className="lock-profile" data-checking={pending}>
        <div className="lock-avatar">{data.preferences.avatar ? <img src={data.preferences.avatar} alt="" /> : <UserRound size={48} aria-hidden="true" />}</div>
        <h1 id="unlock-title">{data.preferences.nickname || "Calix"}</h1>
      </div></> : <><span className="security-symbol"><LockKeyhole size={26} /></span><h1 id="unlock-title">{t(title)}</h1></>}
      <form className={migrating ? "credential-migration" : undefined} onSubmit={event => {
        event.preventDefault();
        if (pending) return;
        if (migrating && replacement !== confirmation) {
          setError("새 비밀번호가 일치하지 않습니다.");
          return;
        }
        setPending(true);
        setError("");
        void mutate("security.unlock", { password, scope, ...(migrating ? { replacement, mode } : {}) }).then(() => {
          setPassword("");
          const reminders = data.preferences.reminders;
          stopErrorCue();
          playLogonCue(reminders?.enabled !== false && reminders?.sound !== false, reminders?.volume);
        })
          .catch(reason => setError(reason.message)).finally(() => setPending(false));
      }}>
        {migrating && <h2>{t("새 잠금 방식 설정")}</h2>}
        <CredentialInput label={migrating ? "현재 비밀번호" : currentMode?.startsWith("pin") ? "PIN" : "비밀번호"}
          mode={currentMode} value={password} onChange={setPassword} current autoFocus />
        {migrating && <>
          <CredentialPicker mode={mode} onChange={next => { setMode(next); setReplacement(""); setConfirmation(""); }} pinSupported={data.security?.pin_supported} />
          <CredentialInput label={mode === "password" ? "새 비밀번호" : "새 PIN"} mode={mode} value={replacement} onChange={setReplacement} />
          <CredentialInput label={mode === "password" ? "비밀번호 확인" : "PIN 확인"} mode={mode} value={confirmation} onChange={setConfirmation} />
          {mode !== "password" && <p className="muted">{t("PIN과 PIN으로 보호한 백업은 현재 Windows 계정에 연결됩니다.")}</p>}
        </>}
        {error && <p role="alert">{t(error)}</p>}
        <button className="button primary" disabled={pending}>{pending ? t("확인 중") : t(migrating ? "저장하고 잠금 해제" : "잠금 해제")}</button>
      </form>
      {main && <div className="lock-actions">
        <button type="button" className="text-button" disabled={pending} onClick={() => setReset(true)}>{t("비밀번호를 잊으셨나요?")}</button>
        {onExit && <button type="button" className="text-button" onClick={onExit}>{t("종료")}</button>}
      </div>}
    </section>
    {reset && <LockedResetDialog onClose={() => setReset(false)} />}
  </>;
}

export function ProtectedSection({ scope, children }: { scope: "timetable" | "grades"; children: ReactNode }) {
  useLanguage();
  const { data } = useCalix();
  const security = data.security;
  if (scope === "grades" && !security?.configured) {
    return <section className="grade-password-required">
      <header className="page-heading"><div><h1>{t("학점 메뉴")}</h1><p className="muted">{t("학점 계산에는 비밀번호가 필요합니다.")}</p></div></header>
      <SecuritySettings />
    </section>;
  }
  return security?.configured && security.policy[scope] && !security.unlocked.includes(scope)
    ? <UnlockView scope={scope} /> : <>{children}</>;
}

export function SecuritySettings() {
  useLanguage();
  const { data, mutate, notify } = useCalix();
  const current = data.security;
  const [policy, setPolicy] = useState(current?.policy ?? { main: false, timetable: false, grades: false, idle_minutes: 5 });
  const [password, setPassword] = useState("");
  const [replacement, setReplacement] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);
  const configured = !!current?.configured;
  const [mode, setMode] = useState<CredentialMode>(current?.credential_mode === "legacy" ? "password" : current?.credential_mode ?? "password");
  const newPassword = configured ? replacement : password;
  const changingMode = configured && mode !== current?.credential_mode && current?.credential_mode !== undefined;
  const [custom, setCustom] = useState(![1, 5, 10, 15, 30, 60].includes(policy.idle_minutes));
  return (
    <section className="glass settings-panel security-settings">
      <div className="settings-heading"><ShieldCheck aria-hidden="true" /><h2>{t("비밀번호와 잠금")}</h2>{configured && <span className="security-status">{t("암호화 사용 중")}</span>}</div>
      <form onSubmit={event => {
        event.preventDefault();
        if (newPassword && newPassword !== confirm) { notify("새 비밀번호가 일치하지 않습니다.", true); return; }
        setPending(true);
        void mutate(configured ? "security.configure" : "security.setup",
          configured ? { password, replacement: replacement || undefined, mode: replacement ? mode : undefined, policy } : { password, policy, mode })
          .then(() => { setPassword(""); setReplacement(""); setConfirm(""); notify("잠금 설정 저장됨"); })
          .catch(() => {}).finally(() => setPending(false));
      }}>
        <fieldset disabled={pending}>
          {configured && <CredentialInput label={current?.credential_mode?.startsWith("pin") ? "현재 PIN" : "현재 비밀번호"}
            mode={current?.credential_mode} value={password} onChange={setPassword} current />}
          <CredentialPicker mode={mode} onChange={next => { setMode(next); setReplacement(""); setConfirm(""); if (!configured) setPassword(""); }} pinSupported={current?.pin_supported} />
          <CredentialInput label={mode === "password" ? "새 비밀번호" : "새 PIN"} mode={mode}
            value={newPassword} onChange={configured ? setReplacement : setPassword} required={!configured || changingMode} />
          {(!configured || changingMode || replacement) && <CredentialInput
            label={mode === "password" ? "비밀번호 확인" : "PIN 확인"} mode={mode} value={confirm} onChange={setConfirm} />}
          {mode !== "password" && <p className="muted">{t("PIN과 PIN으로 보호한 백업은 현재 Windows 계정에 연결됩니다.")}</p>}
          <div className="security-options">
            {([["main", "메인 화면 자동 잠금"], ["timetable", "시간표 잠금"], ["grades", "학점 메뉴 잠금"]] as const).map(([key, label]) =>
              <div className="setting-row security-option" key={key}>
                <strong>{t(label)}</strong>
                <button type="button" role="switch" aria-label={t(label)} aria-checked={policy[key]} className={`switch ${policy[key] ? "on" : ""}`} onClick={() => setPolicy(previous => ({ ...previous, [key]: !previous[key] }))}><i /></button>
              </div>)}
          </div>
          {policy.main && <div className="security-time">
            <label>{t("미사용 시간")}<select aria-label={t("미사용 시간")} value={custom ? "custom" : String(policy.idle_minutes)} onChange={event => {
              setCustom(event.target.value === "custom");
              if (event.target.value !== "custom") setPolicy(previous => ({ ...previous, idle_minutes: Number(event.target.value) }));
            }}>{[1, 5, 10, 15, 30, 60].map(minutes => <option key={minutes} value={minutes}>{minutes}{t("분")}</option>)}<option value="custom">{t("직접 입력")}</option></select></label>
            {custom && <label>{t("분")}<NumberField aria-label={t("자동 잠금 분")} min={1} max={1440} required value={policy.idle_minutes} onValueChange={value => setPolicy(previous => ({ ...previous, idle_minutes: value }))} /></label>}
          </div>}
          <p className="security-warning">{t("초기화하면 저장 데이터가 삭제됩니다.")}</p>
          <p className="muted">{t("암호화 자료는 1.6.0 이상에서 열 수 있습니다.")}</p>
          <div className="dialog-actions security-actions"><button type="submit" className="button primary">{pending ? t("저장 중") : configured ? t("설정 저장") : t("비밀번호 설정")}</button></div>
        </fieldset>
      </form>
    </section>
  );
}

export function SecurityMonitor({ state, beforeLock, refresh }: {
  state: SecurityState | undefined;
  beforeLock: () => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const callbacks = useRef({ beforeLock, refresh });
  callbacks.current = { beforeLock, refresh };
  useEffect(() => {
    if (!state?.configured || state.locked) return;
    let lastActivity = performance.now();
    let lastSent = 0;
    let checking = false;
    let active = true;
    const activity = () => {
      lastActivity = performance.now();
      if (lastActivity - lastSent >= 1000) {
        lastSent = lastActivity;
        void rpc("security.activity").catch(() => {});
      }
    };
    const check = async () => {
      if (checking) return;
      checking = true;
      try {
        if (state.policy.main && performance.now() - lastActivity >= Math.max(1000, state.policy.idle_minutes * 60000 - 4000)) {
          await callbacks.current.beforeLock();
          if (!active) return;
          await rpc("security.lock", { scope: "main" });
        }
        const current = await rpc<SecurityState>("security.state");
        if (current.locked && active) {
          if (isTauri()) await invoke("privacy_lock").catch(() => {});
          await callbacks.current.refresh();
        }
      } finally {
        checking = false;
      }
    };
    const events = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart"] as const;
    for (const name of events) window.addEventListener(name, activity, { passive: true });
    const timer = setInterval(() => { void check().catch(() => {}); }, 1000);
    return () => {
      active = false;
      clearInterval(timer);
      for (const name of events) window.removeEventListener(name, activity);
    };
  }, [state?.configured, state?.locked, state?.policy.main, state?.policy.idle_minutes]);
  return null;
}
