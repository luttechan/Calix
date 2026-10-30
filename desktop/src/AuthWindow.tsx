import { useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { ArrowUpRight, Check, LoaderCircle, RefreshCw, X } from "lucide-react";

export function AuthWindow() {
  const host = useRef<HTMLDivElement>(null),
    [loaded, setLoaded] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    document.documentElement.dataset.theme = params.get("theme") || "pink";
    document.documentElement.dataset.font = params.get("font") || "pretendard";
    document.documentElement.dataset.glass = "true";
    if (!isTauri()) {
      setLoaded(true);
      return;
    }
    let active = true,
      frame = 0;
    const cleanups: (() => void)[] = [];
    for (const [event, handler] of [
      ["auth:page", (value: { loaded: boolean }) => setLoaded(value.loaded)],
      [
        "auth:status",
        (value: { success: boolean; message: string }) => {
          setBusy(false);
          setError(value.success ? "" : value.message);
        },
      ],
      [
        "auth:theme",
        (value: { theme: string; font: string }) => {
          if (value.theme) document.documentElement.dataset.theme = value.theme;
          if (value.font) document.documentElement.dataset.font = value.font;
        },
      ],
    ] as const) {
      void listen(event, (message) => {
        if (active) (handler as (value: unknown) => void)(message.payload);
      }).then((unlisten) => {
        if (active) cleanups.push(unlisten);
        else unlisten();
      });
    }
    const resize = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!host.current || !active) return;
        const { x, y, width, height } = host.current.getBoundingClientRect();
        void invoke("auth_mount", { bounds: { x, y, width, height } }).catch(
          (error) => {
            if (active) setError(String(error));
          },
        );
      });
    };
    const observer = new ResizeObserver(resize);
    if (host.current) observer.observe(host.current);
    window.addEventListener("resize", resize);
    resize();
    return () => {
      active = false;
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", resize);
      cleanups.forEach((cleanup) => cleanup());
    };
  }, []);
  const close = () => {
    if (isTauri()) void getCurrentWindow().close();
  };
  const complete = () => {
    setBusy(true);
    setError("");
    void invoke("auth_complete").catch((error) => {
      setBusy(false);
      setError(String(error));
    });
  };
  return (
    <div className="auth-shell app-shell">
      <div className="auth-workspace">
        <header className="auth-header" data-tauri-drag-region>
          <div className="auth-brand" data-tauri-drag-region>
            <img src="/assets/icons/calix.svg" alt="" />
            <span>Calix</span>
            <small>로그인</small>
          </div>
          <button
            className="icon-button"
            aria-label="닫기"
            title="닫기"
            onClick={close}
          >
            <X size={20} />
          </button>
        </header>
        <section className="auth-heading">
          <div>
            <p className="eyebrow">부산외대 Canvas</p>
            <h1>학교 계정으로 로그인</h1>
          </div>
          <span className="auth-connection">
            {loaded ? (
              <Check size={15} />
            ) : (
              <LoaderCircle size={15} className="spin" />
            )}
            {loaded ? "학교 화면" : "연결 중"}
          </span>
        </section>
        <div className="auth-browser-frame glass">
          <div className="auth-browser-host" ref={host}>
            {!loaded && (
              <div className="auth-placeholder">
                <LoaderCircle size={25} className="spin" />
              </div>
            )}
            {!isTauri() && (
              <div className="auth-placeholder">
                Windows 앱에서 학교 계정으로 로그인합니다.
              </div>
            )}
          </div>
        </div>
        <footer className="auth-footer">
          <div role="status" className={error ? "danger" : "muted"}>
            {error ||
              (busy ? "로그인 확인 중" : "학교 로그인 후 완료를 누르세요.")}
          </div>
          <button
            className="quiet"
            disabled={busy}
            onClick={() => {
              setLoaded(false);
              setError("");
              void invoke("auth_reload").catch((error) =>
                setError(String(error)),
              );
            }}
          >
            <RefreshCw size={16} />
            새로고침
          </button>
          <button
            className="primary"
            disabled={busy || !loaded || !isTauri()}
            onClick={complete}
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <ArrowUpRight size={16} />
            )}
            로그인 완료
          </button>
        </footer>
      </div>
    </div>
  );
}
