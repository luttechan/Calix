import { t, useLanguage } from "./i18n";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowLeft,
  Check,
  LoaderCircle,
  UserRound,
  Trash2,
} from "lucide-react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { Modal, useCalix } from "./App";
import { readAvatar } from "./avatar";
const themes = [
  ["pink", "핑크", "#d09bb7"],
  ["sky", "스카이블루", "#9bb8db"],
  ["mint", "민트", "#9bcdb9"],
  ["purple", "퍼플", "#b7a0d4"],
  ["dark", "다크", "#333242"],
    ["peach", "피치", "#deaa92"],
    ["amber", "앰버", "#d7b16a"],
    ["olive", "올리브", "#a7b580"],
    ["lavender", "라벤더", "#aaa7dc"],
] as const;
export function Onboarding() {
  useLanguage();
  const { data, mutate } = useCalix(),
    dialog = useRef<HTMLDialogElement>(null);
  const [step, setStep] = useState(0),
    [nickname, setNickname] = useState(data.preferences.nickname),
    [theme, setTheme] = useState(data.preferences.theme),
    [saving, setSaving] = useState(false);
  useEffect(() => {
    const open = () => {
      if (!document.getElementById("calix-startup")) {
        if (!dialog.current?.open) dialog.current?.showModal();
        return true;
      }
      return false;
    };
    const observer = new MutationObserver(() => {
      if (open()) observer.disconnect();
    });
    if (!open()) observer.observe(document.body, { childList: true });
    return () => {
      observer.disconnect();
      dialog.current?.close();
    };
  }, []);
  const finish = async () => {
    setSaving(true);
    try {
      await mutate("onboarding.finish", { nickname, theme });
    } catch {
    } finally {
      setSaving(false);
    }
  };
  return (
    <dialog
      ref={dialog}
      className="onboarding"
      onCancel={(event) => event.preventDefault()}
      style={
        {
          "--setup-color": themes.find((row) => row[0] === theme)?.[2],
        } as React.CSSProperties
      }
    >
      <div className="setup-orbit" aria-hidden="true" />
      <div className="setup-brand">
        <img src="/assets/icons/calix.svg" alt="" />
        Calix
      </div>
      <form
        className="setup-card"
        onSubmit={(event) => {
          event.preventDefault();
          if (step === 0) setStep(1);
          else void finish();
        }}
      >
        <div className="setup-symbol" aria-hidden="true">
          {step === 0 ? (
            <UserRound size={32} />
          ) : (
            <img src="/assets/icons/calix.svg" alt="" />
          )}
        </div>
        <h1>{step === 0 ? t("닉네임 설정") : t("테마 선택")}</h1>
        {step === 0 ? (
          <label className="setup-name">
            <input
              aria-label={t("닉네임")}
              autoFocus
              required
              maxLength={30}
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              placeholder={t("닉네임")}
              autoComplete="nickname"
            />
          </label>
        ) : (
            <div className="setup-themes">
              {themes.map(([id, label, color]) => (
                <button
                  type="button"
                  key={id}
                  aria-pressed={theme === id}
                  className={theme === id ? "selected" : ""}
                  onClick={() => {
                    setTheme(id);
                    document.documentElement.dataset.theme = id;
                  }}
                >
                  <span style={{ background: color }}>
                    {theme === id && <Check size={22} />}
                  </span>
                  {t(label)}
                </button>
              ))}
            </div>
        )}
        <div className="setup-actions">
          {step === 1 && (
            <button
              type="button"
              className="quiet"
              disabled={saving}
              onClick={() => setStep(0)}
            >
              <ArrowLeft size={17} />{t("이전")}{" "}</button>
          )}
          <span />
          <button className="primary" disabled={!nickname.trim() || saving}>
            {saving ? (
              <LoaderCircle size={18} className="spin" />
            ) : step === 0 ? (
              t("계속")
            ) : (
              t("시작하기")
            )}
            <ArrowRight size={17} />
          </button>
        </div>
        <div className="setup-progress" aria-label={t("{0}/2 단계", [String(step + 1)])}>
          <i className={step === 0 ? "active" : ""} />
          <i className={step === 1 ? "active" : ""} />
        </div>
      </form>
    </dialog>
  );
}
export function ProfileSettings() {
  useLanguage();
  const photoInput = useRef<HTMLInputElement>(null);
  const photoRevision = useRef(0);
  const [avatar, setAvatar] = useState("");
  const [photoLoading, setPhotoLoading] = useState(false);
  useEffect(
    () => () => {
      photoRevision.current++;
    },
    [],
  );
  const { data, mutate, notify } = useCalix(),
    [nickname, setNickname] = useState(data.preferences.nickname),
    [greeting, setGreeting] = useState(data.preferences.greeting),
    [saving, setSaving] = useState(false);
  useEffect(
    () => setAvatar(data.preferences.avatar || ""),
    [data.preferences.avatar],
  );
  const choosePhoto = async (file?: File) => {
    if (!file) return;
    const generation = ++photoRevision.current;
    setPhotoLoading(true);
    try {
      const value = await readAvatar(file);
      if (generation === photoRevision.current) setAvatar(value);
    } catch (error) {
      if (generation === photoRevision.current)
        notify(
          error instanceof Error
            ? error.message
            : t("사진을 불러오지 못했습니다."),
        );
    } finally {
      if (generation === photoRevision.current) setPhotoLoading(false);
    }
  };
  const save = async () => {
    if (photoLoading || saving) return;
    setSaving(true);
    try {
      await mutate("profile.save", { nickname, greeting, avatar });
      notify("저장됨");
    } catch {
    } finally {
      setSaving(false);
    }
  };
  return (
    <>
      <section className="glass settings-panel profile-settings">
        <div className="settings-heading"><UserRound aria-hidden="true" /><h2>{t("내 프로필")}</h2></div>
        <div className="profile-photo-editor">
          <span className="profile-photo-preview">
            {avatar ? (
              <img src={avatar} alt={t("내 프로필 사진")} />
            ) : (
              <UserRound size={30} />
            )}
          </span>
          <div>
            <button
              type="button"
              disabled={photoLoading}
              onClick={() => photoInput.current?.click()}
            >
              {photoLoading ? t("불러오는 중") : t("사진 선택")}
            </button>
            {avatar && (
              <button
                type="button"
                className="quiet"
                disabled={photoLoading}
                onClick={() => setAvatar("")}
              >{t("사진 삭제")}{" "}</button>
            )}
          </div>
          <input
            ref={photoInput}
            type="file"
            accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
            aria-label={t("프로필 사진 선택")}
            hidden
            onChange={(event) => {
              void choosePhoto(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <label>{t("닉네임")}{" "}<input
              required
              maxLength={30}
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
            />
          </label>
          <label>{t("홈 문구")}{" "}<textarea
              aria-label={t("홈 문구")}
              required
              maxLength={120}
              rows={2}
              value={greeting}
              onChange={(event) => setGreeting(event.target.value)}
            />
          </label>
          <p className="muted profile-placeholder">
            {t("{닉네임}")}{" "}{t("은 닉네임으로 바뀝니다.")}{" "}</p>
          <div className="greeting-preview">
            {greeting.replaceAll("{닉네임}", nickname || "나")}
          </div>
          <div className="dialog-actions">
            <span />
            <button
              className="primary"
              disabled={
                saving || photoLoading || !nickname.trim() || !greeting.trim()
              }
            >{t("저장")}{" "}</button>
          </div>
        </form>
      </section>
    </>
  );
}

export function ResetSettings() {
  useLanguage();
  const { mutate, resetView, notify } = useCalix();
  const [reset, setReset] = useState(false),
    [confirmed, setConfirmed] = useState(false),
    [resetting, setResetting] = useState(false);
  const erase = async () => {
    setResetting(true);
    try {
      if (isTauri()) await invoke("auth_logout");
      await mutate("data.reset", { confirmation: "초기화" });
      resetView();
      setReset(false);
    } catch (error) {
      notify(String(error), true);
    } finally {
      setResetting(false);
    }
  };
  return (
    <>
      <section className="glass settings-panel reset-panel">
        <div>
          <h2>{t("DB 초기화")}</h2>
          <p>{t("일정, 체크리스트, 시간표와 일기를 삭제합니다.")}</p>
        </div>
        <button
          className="danger-button"
          onClick={() => {
            setConfirmed(false);
            setReset(true);
          }}
        >
          <Trash2 size={16} />{t("초기화")}{" "}</button>
      </section>
      {reset && (
        <Modal
          title={t("모든 자료를 삭제하시겠습니까?")}
          onClose={() => {
            if (!resetting) setReset(false);
          }}
        >
          <div className="reset-warning">
            <Trash2 size={30} />
            <strong>{t("초기화 후 복구할 수 없습니다.")}</strong>
            <p>{t("모든 계정의 앱 자료와 로그인 정보가 삭제됩니다. 별도로 내보낸 백업 파일은 유지됩니다.")}{" "}</p>
          </div>
          <label className="reset-confirm">
            <input
              type="checkbox"
              checked={confirmed}
              disabled={resetting}
              onChange={(event) => setConfirmed(event.target.checked)}
            />{t("복구할 수 없음을 확인했습니다.")}{" "}</label>
          <div className="dialog-actions">
            <span />
            <button disabled={resetting} onClick={() => setReset(false)}>{t("취소")}{" "}</button>
            <button
              className="danger-button"
              disabled={!confirmed || resetting}
              onClick={() => void erase()}
            >
              {resetting ? t("초기화 중") : t("DB 초기화")}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
