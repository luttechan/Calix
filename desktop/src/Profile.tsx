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
const themes = [
  ["pink", "핑크", "#d09bb7"],
  ["sky", "스카이블루", "#9bb8db"],
  ["mint", "민트", "#9bcdb9"],
  ["purple", "퍼플", "#b7a0d4"],
  ["dark", "다크", "#333242"],
] as const;
export function Onboarding() {
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
        <p className="eyebrow">{step === 0 ? "반갑습니다" : "나만의 Calix"}</p>
        <h1>{step === 0 ? "어떻게 불러드릴까요?" : "어떤 색이 좋으세요?"}</h1>
        {step === 0 ? (
          <label className="setup-name">
            닉네임
            <input
              aria-label="닉네임"
              autoFocus
              required
              maxLength={30}
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              placeholder="닉네임"
              autoComplete="nickname"
            />
          </label>
        ) : (
          <>
            <p className="setup-greeting">{nickname.trim()}님, 오셨군요!</p>
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
                  {label}
                </button>
              ))}
            </div>
          </>
        )}
        <div className="setup-actions">
          {step === 1 && (
            <button
              type="button"
              className="quiet"
              disabled={saving}
              onClick={() => setStep(0)}
            >
              <ArrowLeft size={17} />
              이전
            </button>
          )}
          <span />
          <button className="primary" disabled={!nickname.trim() || saving}>
            {saving ? (
              <LoaderCircle size={18} className="spin" />
            ) : step === 0 ? (
              "계속"
            ) : (
              "시작하기"
            )}
            <ArrowRight size={17} />
          </button>
        </div>
        <div className="setup-progress" aria-label={`${step + 1}/2 단계`}>
          <i className={step === 0 ? "active" : ""} />
          <i className={step === 1 ? "active" : ""} />
        </div>
      </form>
    </dialog>
  );
}
export function ProfileSettings() {
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
  const { data, mutate, notify, leave, draft, resetView } = useCalix(),
    [nickname, setNickname] = useState(data.preferences.nickname),
    [greeting, setGreeting] = useState(data.preferences.greeting),
    [saving, setSaving] = useState(false),
    [reset, setReset] = useState(false),
    [confirmed, setConfirmed] = useState(false),
    [resetting, setResetting] = useState(false);
  useEffect(
    () => setAvatar(data.preferences.avatar || ""),
    [data.preferences.avatar],
  );
  const choosePhoto = async (file?: File) => {
    if (!file) return;
    const generation = ++photoRevision.current;
    if (
      file.size > 5 * 1024 * 1024 ||
      !["image/png", "image/jpeg", "image/webp"].includes(file.type)
    ) {
      notify("5MB 이하의 PNG, JPG, WebP 사진을 선택하세요.");
      return;
    }
    setPhotoLoading(true);
    const url = URL.createObjectURL(file);
    const image = new Image();
    try {
      image.src = url;
      await image.decode();
      if (image.naturalWidth * image.naturalHeight > 25000000)
        throw Error("사진 크기가 너무 큽니다.");
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 256;
      const context = canvas.getContext("2d");
      if (!context) throw Error("사진을 불러오지 못했습니다.");
      const side = Math.min(image.naturalWidth, image.naturalHeight);
      context.drawImage(
        image,
        (image.naturalWidth - side) / 2,
        (image.naturalHeight - side) / 2,
        side,
        side,
        0,
        0,
        256,
        256,
      );
      if (generation === photoRevision.current)
        setAvatar(canvas.toDataURL("image/png"));
    } catch (error) {
      if (generation === photoRevision.current) notify(String(error));
    } finally {
      image.src = "";
      URL.revokeObjectURL(url);
      if (generation === photoRevision.current) setPhotoLoading(false);
    }
  };
  const save = async () => {
    setSaving(true);
    try {
      await mutate("profile.save", { nickname, greeting, avatar });
      notify("저장됨");
    } catch {
    } finally {
      setSaving(false);
    }
  };
  const erase = async () => {
    setResetting(true);
    try {
      if (isTauri()) await invoke("auth_logout");
      await mutate("data.reset", { confirmation: "초기화" });
      resetView();
      setReset(false);
    } catch (error) {
      notify(String(error));
    } finally {
      setResetting(false);
    }
  };
  return (
    <>
      <section className="glass settings-panel profile-settings">
        <h2>내 Calix</h2>
        <div className="profile-photo-editor">
          <span className="profile-photo-preview">
            {avatar ? (
              <img src={avatar} alt="내 프로필 사진" />
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
              {photoLoading ? "불러오는 중" : "사진 선택"}
            </button>
            {avatar && (
              <button
                type="button"
                className="quiet"
                disabled={photoLoading}
                onClick={() => setAvatar("")}
              >
                사진 삭제
              </button>
            )}
          </div>
          <input
            ref={photoInput}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label="프로필 사진 선택"
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
          <label>
            닉네임
            <input
              required
              maxLength={30}
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
            />
          </label>
          <label>
            홈 문구
            <textarea
              aria-label="홈 문구"
              required
              maxLength={120}
              rows={2}
              value={greeting}
              onChange={(event) => setGreeting(event.target.value)}
            />
          </label>
          <p className="muted profile-placeholder">
            {"{닉네임}"} 자리에 닉네임이 표시됩니다.
          </p>
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
            >
              저장
            </button>
          </div>
        </form>
      </section>
      <section className="glass settings-panel reset-panel">
        <div>
          <h2>DB 초기화</h2>
          <p>일정, 체크리스트, 시간표와 일기를 삭제합니다.</p>
        </div>
        <button
          className="danger-button"
          onClick={() => {
            setConfirmed(false);
            setReset(true);
          }}
        >
          <Trash2 size={16} />
          초기화
        </button>
      </section>
      {reset && (
        <Modal
          title="모든 자료를 삭제하시겠습니까?"
          onClose={() => {
            if (!resetting) setReset(false);
          }}
        >
          <div className="reset-warning">
            <Trash2 size={30} />
            <strong>초기화 후 복구할 수 없습니다.</strong>
            <p>
              모든 계정의 앱 자료와 로그인 정보가 삭제됩니다. 별도로 내보낸 백업
              파일은 유지됩니다.
            </p>
          </div>
          <label className="reset-confirm">
            <input
              type="checkbox"
              checked={confirmed}
              disabled={resetting}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            복구할 수 없음을 확인했습니다.
          </label>
          <div className="dialog-actions">
            <span />
            <button disabled={resetting} onClick={() => setReset(false)}>
              취소
            </button>
            <button
              className="danger-button"
              disabled={!confirmed || resetting}
              onClick={() => void erase()}
            >
              {resetting ? "초기화 중" : "DB 초기화"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
