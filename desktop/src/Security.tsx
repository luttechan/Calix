import { locale, t, useLanguage } from "./i18n";
import { PageHeading } from "./PageHeading";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { LockKeyhole, ShieldCheck, TriangleAlert, UserRound } from "lucide-react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { Modal, useCalix } from "./App";
import { rpc } from "./bridge";
import { NumberField } from "./NumberField";
import { PinField, PinKeypad, pinLength, validPin } from "./PinKeypad";
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
  const digits = pinLength(mode);
  if (digits) return <PinField key={mode} title={t(label)} value={value} length={digits} onChange={onChange} />;
  return <label>{t(label)}<input type="password" autoComplete={current ? "current-password" : "new-password"}
    minLength={!current ? 6 : undefined} maxLength={1024}
    value={value} required={required} autoFocus={autoFocus} onChange={event => onChange(event.target.value)} /></label>;
}

export function CredentialPrompt({ label, mode, pending, error, nextLabel = "다음", minimum = 1, onSubmit }: {
  label: string;
  mode?: CredentialMode | "legacy";
  pending: boolean;
  error?: string;
  nextLabel?: string;
  minimum?: number;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState("");
  const digits = pinLength(mode);
  const submit = (secret: string) => {
    if (pending || secret.length < minimum || !validPin(mode, secret)) return;
    setValue("");
    onSubmit(secret);
  };
  return <form className="credential-prompt" onSubmit={event => { event.preventDefault(); submit(value); }}>
    {digits ? <PinKeypad label={t(label)} value={value} length={digits} pending={pending}
      invalid={!!error} autoFocus onChange={next => { setValue(next); if (next.length === digits) submit(next); }} />
      : <label>{t(label)}<input type="password" aria-label={t(label)} autoComplete="off" autoFocus
        minLength={minimum} maxLength={1024} required disabled={pending} value={value}
        onChange={event => setValue(event.target.value)} /></label>}
    {error && <p className="danger" role="alert">{t(error)}</p>}
    {!digits && <button type="submit" className="primary" disabled={pending || value.length < minimum}>
      {pending ? t("확인 중") : t(nextLabel)}
    </button>}
  </form>;
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
  const unlocking = useRef(false);
  const [error, setError] = useState("");
  const [reset, setReset] = useState(false);
  const [mode, setMode] = useState<CredentialMode>("password");
  const [replacement, setReplacement] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const title = scope === "main" ? "Calix 잠금" : scope === "timetable" ? "시간표 잠금" : "학점 메뉴 잠금";
  const main = scope === "main";
  const migrating = main && data.security?.credential_mode === "legacy";
  const currentMode = data.security?.credential_mode;
  const digits = pinLength(currentMode);
  const unlock = (secret: string) => {
    if (unlocking.current || !validPin(currentMode, secret)) return;
    if (migrating && !validPin(mode, replacement)) {
      setError("선택한 자릿수만큼 숫자를 입력하세요.");
      return;
    }
    if (migrating && replacement !== confirmation) {
      setError("새 비밀번호가 일치하지 않습니다.");
      return;
    }
    unlocking.current = true;
    setPending(true);
    setError("");
    void mutate("security.unlock", { password: secret, scope, ...(migrating ? { replacement, mode } : {}) },
      { inlineError: true }).then(() => {
      setPassword("");
      const reminders = data.preferences.reminders;
      stopErrorCue();
      playLogonCue(reminders?.enabled !== false && reminders?.sound !== false, reminders?.volume);
    }).catch(reason => {
      if (digits) setPassword("");
      setError(reason.message);
    }).finally(() => {
      unlocking.current = false;
      setPending(false);
    });
  };
  return <>
    <section className={`unlock-view${main ? " startup-unlock" : ""}${main && digits ? " startup-unlock--pin" : ""}${migrating ? " startup-migration" : ""}`} aria-labelledby="unlock-title">
      {main ? <><LockClock /><div className="lock-profile" data-checking={pending}>
        <div className="lock-avatar">{data.preferences.avatar ? <img src={data.preferences.avatar} alt="" /> : <UserRound size={48} aria-hidden="true" />}</div>
        <h1 id="unlock-title">{data.preferences.nickname || "Calix"}</h1>
      </div></> : <><span className="security-symbol"><LockKeyhole size={26} /></span><h2 id="unlock-title">{t(title)}</h2></>}
      <form className={migrating ? "credential-migration" : undefined} onSubmit={event => {
        event.preventDefault();
        unlock(password);
      }}>
        {migrating && <h2>{t("새 잠금 방식 설정")}</h2>}
        {digits ? <PinKeypad label={t("PIN")} value={password} length={digits} pending={pending}
          invalid={!!error} autoFocus onChange={value => {
            if (unlocking.current) return;
            setPassword(value);
            setError("");
            if (value.length === digits) unlock(value);
          }} /> : <CredentialInput label={migrating ? "현재 비밀번호" : "비밀번호"}
          mode={currentMode} value={password} onChange={setPassword} current autoFocus />}
        {migrating && <>
          <CredentialPicker mode={mode} onChange={next => { setMode(next); setReplacement(""); setConfirmation(""); }} pinSupported={data.security?.pin_supported} />
          <CredentialInput label={mode === "password" ? "새 비밀번호" : "새 PIN"} mode={mode} value={replacement} onChange={setReplacement} />
          <CredentialInput label={mode === "password" ? "비밀번호 확인" : "PIN 확인"} mode={mode} value={confirmation} onChange={setConfirmation} />
        </>}
        {error && <p role="alert">{t(error)}</p>}
        {digits
          ? pending && <p className="pin-pending" role="status">{t("확인 중")}</p>
          : <button className="button primary" disabled={pending}>{pending ? t("확인 중") : t(migrating ? "저장하고 잠금 해제" : "잠금 해제")}</button>}
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
    return <>
      <PageHeading title={t("학점 계산기")} />
      <section className="grade-password-required">
        <p className="muted">{t("학점 계산에는 비밀번호가 필요합니다.")}</p>
        <SecuritySettings />
      </section>
    </>;
  }
  if (security?.configured && security.policy[scope] && !security.unlocked.includes(scope)) {
    return <>
      <PageHeading title={t(scope === "grades" ? "학점 계산기" : "시간표")} />
      <UnlockView scope={scope} />
    </>;
  }
  return <>{children}</>;
}

type CredentialAction = "setup" | "change" | "method" | "policy";

function CredentialWizard({ action, policy, onClose }: {
  action: CredentialAction;
  policy: SecurityState["policy"];
  onClose: () => void;
}) {
  const { data, mutate, notify, soundError } = useCalix();
  const current = data.security;
  const [mode, setMode] = useState<CredentialMode>(current?.credential_mode === "legacy" ? "password" : current?.credential_mode ?? "password");
  const [step, setStep] = useState<"method" | "current" | "new" | "confirm">(action === "setup" ? "method" : "current");
  const [previous, setPrevious] = useState("");
  const [replacement, setReplacement] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const pin = Boolean(pinLength(mode));
  const label = step === "current" ? (pinLength(current?.credential_mode) ? "현재 PIN" : "현재 비밀번호")
    : step === "new" ? (pin ? "새 PIN" : "새 비밀번호") : (pin ? "PIN 확인" : "비밀번호 확인");
  const save = async (params: Record<string, unknown>) => {
    setPending(true);
    setError("");
    try {
      await mutate(action === "setup" ? "security.setup" : "security.configure", params, { inlineError: true });
      notify(action === "policy" ? "잠금 설정 저장됨" : "저장됨");
      onClose();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setPending(false);
    }
  };
  const submit = async (value: string) => {
    setError("");
    if (step === "current") {
      if (action === "policy") { await save({ password: value, policy }); return; }
      setPending(true);
      try {
        await rpc("security.verify", { password: value });
        setPrevious(value);
        setStep(action === "method" ? "method" : "new");
      } catch (error) {
        setError((error as Error).message);
        soundError();
      } finally {
        setPending(false);
      }
    } else if (step === "new") {
      setReplacement(value);
      setStep("confirm");
    } else if (value !== replacement) {
      setError(pin ? "PIN이 일치하지 않습니다." : "새 비밀번호가 일치하지 않습니다.");
      soundError();
    } else {
      await save(action === "setup" ? { password: replacement, mode, policy }
        : { password: previous, replacement, mode, policy: current?.policy ?? policy });
    }
  };
  return <Modal title={t(step === "method" ? "잠금 방식" : label)} className="credential-wizard" onClose={() => { if (!pending) onClose(); }}>
    <div className="credential-wizard-step" key={step}>
      {step === "method" ? <>
        <CredentialPicker mode={mode} onChange={setMode} pinSupported={current?.pin_supported} />
        <button className="primary" type="button" onClick={() => setStep("new")}>{t("다음")}</button>
      </> : <CredentialPrompt label={label} mode={step === "current" ? current?.credential_mode : mode}
        minimum={step === "current" || pin ? 1 : 6} pending={pending} error={error}
        nextLabel={step === "confirm" || action === "policy" ? "저장" : "다음"} onSubmit={value => void submit(value)} />}
    </div>
  </Modal>;
}

export function SecuritySettings({ setupOnly = false }: { setupOnly?: boolean } = {}) {
  useLanguage();
  const { data } = useCalix();
  const current = data.security;
  const [policy, setPolicy] = useState(current?.policy ?? { main: false, timetable: false, grades: false, idle_minutes: 5 });
  const [action, setAction] = useState<CredentialAction | null>(null);
  const configured = !!current?.configured;
  const [custom, setCustom] = useState(![1, 5, 10, 15, 30, 60].includes(policy.idle_minutes));
  const dirty = current?.policy && (policy.main !== current.policy.main || policy.timetable !== current.policy.timetable ||
    policy.grades !== current.policy.grades || policy.idle_minutes !== current.policy.idle_minutes);
  return (
    <section className="glass settings-panel security-settings">
      {!setupOnly && <div className="settings-heading"><ShieldCheck aria-hidden="true" /><h2>{t("비밀번호와 잠금")}</h2></div>}
      {configured ? <div className="security-credential-actions">
        <button type="button" onClick={() => setAction("change")}>{t(pinLength(current?.credential_mode) ? "PIN 변경" : "비밀번호 변경")}</button>
        <button type="button" onClick={() => setAction("method")}>{t("잠금 방식 변경")}</button>
      </div> : <button className="primary" type="button" onClick={() => setAction("setup")}>{t("비밀번호 설정")}</button>}
      {!setupOnly && <form onSubmit={event => {
        event.preventDefault();
        if (configured && dirty) setAction("policy");
      }}>
        <fieldset>
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
          {configured && <div className="dialog-actions security-actions"><button type="submit" disabled={!dirty} className="button primary">{t("설정 저장")}</button></div>}
        </fieldset>
      </form>}
      {action && <CredentialWizard action={action} policy={policy} onClose={() => setAction(null)} />}
    </section>
  );
}

export function PrivateDiaryMigration({ onClose }: { onClose: () => void }) {
  const { data, mutate, notify } = useCalix();
  const [previous, setPrevious] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const mode = data.security?.credential_mode;
  return <Modal title={t("비밀 일기 암호 변경")} className="credential-wizard"
    onClose={() => { if (!pending) onClose(); }}>
    <div className="credential-wizard-step" key={previous ? "app" : "diary"}>
      {!data.security?.configured ? <SecuritySettings setupOnly /> : !previous
        ? <CredentialPrompt label="기존 비밀 일기 암호" pending={pending} error={error}
          onSubmit={value => { setError(""); setPrevious(value); }} />
        : <CredentialPrompt label={pinLength(mode) ? "현재 PIN" : "현재 비밀번호"} mode={mode}
          pending={pending} nextLabel="변경" onSubmit={password => {
            setPending(true);
            void mutate("vault.migrate", { previous, password }, { inlineError: true })
              .then(() => { notify("비밀 일기 암호 변경됨"); onClose(); })
              .catch((reason: Error) => { setError(reason.message); setPrevious(""); })
              .finally(() => setPending(false));
          }} />}
    </div>
  </Modal>;
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
