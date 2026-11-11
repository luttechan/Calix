import { useEffect, useRef, useState, type ReactNode } from "react";
import { LockKeyhole, ShieldCheck } from "lucide-react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { Modal, useCalix } from "./App";
import { rpc } from "./bridge";
import { NumberField } from "./NumberField";
import type { SecurityState } from "./types";
import "./security-grades.css";

export function UnlockView({ scope = "main" }: { scope?: "main" | "timetable" | "grades" }) {
  const { mutate, notify } = useCalix();
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [reset, setReset] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const title = scope === "main" ? "Calix 잠금" : scope === "timetable" ? "시간표 잠금" : "학점 메뉴 잠금";
  return (
    <section className="unlock-view" aria-labelledby="unlock-title">
      <span className="security-symbol"><LockKeyhole size={26} /></span>
      <h1 id="unlock-title">{title}</h1>
      <form onSubmit={event => {
        event.preventDefault();
        setPending(true);
        setError("");
        void mutate("security.unlock", { password, scope }).then(() => setPassword(""))
          .catch(reason => setError(reason.message)).finally(() => setPending(false));
      }}>
        <label>비밀번호<input type="password" autoComplete="current-password" value={password} maxLength={1024} required autoFocus onChange={event => setPassword(event.target.value)} /></label>
        {error && <p role="alert">{error}</p>}
        <button className="button primary" disabled={pending}>{pending ? "확인 중" : "잠금 해제"}</button>
      </form>
      {scope === "main" && <button type="button" className="text-button" onClick={() => setReset(true)}>비밀번호를 잊으셨나요?</button>}
      {reset && <Modal title="모든 데이터를 초기화하시겠습니까?" onClose={() => setReset(false)}>
        <p>일정, 시간표, 학점, 일기와 비밀번호를 삭제합니다. 복구할 수 없습니다.</p>
        <label>확인 문구<input aria-label="초기화 확인 문구" placeholder="초기화" value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
        <div className="dialog-actions"><button onClick={() => setReset(false)}>취소</button><button className="button danger" disabled={confirmation !== "초기화" || pending} onClick={() => {
          setPending(true);
          void mutate("data.reset", { confirmation: "초기화" }).then(() => notify("초기화됨")).catch(() => {}).finally(() => setPending(false));
        }}>초기화</button></div>
      </Modal>}
    </section>
  );
}

export function ProtectedSection({ scope, children }: { scope: "timetable" | "grades"; children: ReactNode }) {
  const { data } = useCalix();
  const security = data.security;
  if (scope === "grades" && !security?.configured) {
    return <section className="grade-password-required">
      <header className="page-heading"><div><h1>학점 메뉴</h1><p className="muted">비밀번호를 설정하면 학점 메뉴를 사용할 수 있습니다.</p></div></header>
      <SecuritySettings />
    </section>;
  }
  return security?.configured && security.policy[scope] && !security.unlocked.includes(scope)
    ? <UnlockView scope={scope} /> : <>{children}</>;
}

export function SecuritySettings() {
  const { data, mutate, notify } = useCalix();
  const current = data.security;
  const [policy, setPolicy] = useState(current?.policy ?? { main: false, timetable: false, grades: false, idle_minutes: 5 });
  const [password, setPassword] = useState("");
  const [replacement, setReplacement] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);
  const configured = !!current?.configured;
  const newPassword = configured ? replacement : password;
  const [custom, setCustom] = useState(![1, 5, 10, 15, 30, 60].includes(policy.idle_minutes));
  return (
    <section className="security-settings">
      <div className="security-heading"><ShieldCheck size={25} /><div><h2>비밀번호와 잠금</h2><p>{configured ? "저장 데이터 암호화 사용 중" : "비밀번호를 설정하면 저장 데이터를 암호화합니다."}</p></div></div>
      <form onSubmit={event => {
        event.preventDefault();
        if (newPassword && newPassword !== confirm) { notify("새 비밀번호가 일치하지 않습니다."); return; }
        setPending(true);
        void mutate(configured ? "security.configure" : "security.setup",
          configured ? { password, replacement: replacement || undefined, policy } : { password, policy })
          .then(() => { setPassword(""); setReplacement(""); setConfirm(""); notify("잠금 설정 저장됨"); })
          .catch(() => {}).finally(() => setPending(false));
      }}>
        <fieldset disabled={pending}>
          <label>{configured ? "현재 비밀번호" : "비밀번호"}
            <input type="password" autoComplete={configured ? "current-password" : "new-password"} value={password} minLength={configured ? undefined : 12} maxLength={1024} required onChange={event => setPassword(event.target.value)} />
          </label>
          {configured && <label>새 비밀번호<input type="password" autoComplete="new-password" minLength={12} maxLength={1024} value={replacement} onChange={event => setReplacement(event.target.value)} placeholder="변경할 때 입력" /></label>}
          {(!configured || replacement) && <label>비밀번호 확인<input type="password" autoComplete="new-password" value={confirm} required minLength={12} maxLength={1024} onChange={event => setConfirm(event.target.value)} /></label>}
          <p className="muted">12자 이상. 다시 실행할 때 비밀번호가 필요합니다.</p>
          <div className="security-options">
            {([["main", "메인 화면 자동 잠금"], ["timetable", "시간표 잠금"], ["grades", "학점 메뉴 잠금"]] as const).map(([key, label]) =>
              <label className="security-option" key={key}><span>{label}</span><input type="checkbox" checked={policy[key]} onChange={event => setPolicy(previous => ({ ...previous, [key]: event.target.checked }))} /></label>)}
          </div>
          {policy.main && <div className="security-time">
            <label>미사용 시간<select aria-label="미사용 시간" value={custom ? "custom" : String(policy.idle_minutes)} onChange={event => {
              setCustom(event.target.value === "custom");
              if (event.target.value !== "custom") setPolicy(previous => ({ ...previous, idle_minutes: Number(event.target.value) }));
            }}>{[1, 5, 10, 15, 30, 60].map(minutes => <option key={minutes} value={minutes}>{minutes}분</option>)}<option value="custom">직접 입력</option></select></label>
            {custom && <label>분<NumberField aria-label="자동 잠금 분" min={1} max={1440} required value={policy.idle_minutes} onValueChange={value => setPolicy(previous => ({ ...previous, idle_minutes: value }))} /></label>}
          </div>}
          <p className="security-warning">비밀번호를 잊으면 초기화해야 합니다. 초기화 시 저장 데이터가 삭제됩니다.</p>
          <p className="muted">암호화 자료는 1.6.0 이상에서 열 수 있습니다.</p>
          <button className="button primary">{pending ? "암호화 처리 중" : configured ? "설정 저장" : "비밀번호 설정"}</button>
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
