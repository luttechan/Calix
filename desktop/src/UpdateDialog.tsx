import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import { Modal, useCalix } from "./App";
import { rpc, subscribe } from "./bridge";
import { isTauri } from "@tauri-apps/api/core";
type State = {
  phase:
    | "idle"
    | "checking"
    | "current"
    | "available"
    | "downloading"
    | "ready"
    | "error"
    | "manual";
  current: string;
  latest?: string;
  message?: string;
  progress?: number;
};
export function UpdateDialog({
  onClose,
  onInstall,
}: {
  onClose: () => void;
  onInstall: () => void;
}) {
  const { notify } = useCalix(),
    [state, setState] = useState<State>({
      phase: "checking",
      current: "1.4.2",
      message: "업데이트 확인 중",
    }),
    keep = useRef(false);
  useEffect(() => {
    let active = true;
    const unsubscribe = subscribe((message) => {
      if (active && message.event === "update-state")
        setState(message as unknown as State);
    });
    const poll = !isTauri()
      ? setInterval(() => {
          void rpc<State>("update.state")
            .then((value) => {
              if (active) setState(value);
            })
            .catch(() => {});
        }, 300)
      : null;
    void rpc<State>("update.state")
      .then((value) => {
        if (!active) return;
        if (value.phase === "ready") setState(value);
        else return rpc("update.check");
      })
      .catch((error) => {
        if (active)
          setState({
            phase: "error",
            current: "1.4.2",
            message: error.message,
          });
      });
    return () => {
      active = false;
      if (poll) clearInterval(poll);
      unsubscribe();
      void rpc("update.cancel", { keepReady: keep.current }).catch(() => {});
    };
  }, []);
  const working = state.phase === "checking" || state.phase === "downloading";
  return (
    <Modal title="업데이트" onClose={onClose}>
      <div className="update-summary">
        <div className={`update-symbol ${working ? "working" : ""}`}>
          {working ? (
            <LoaderCircle size={28} className="spin" />
          ) : state.phase === "current" ? (
            <Check size={28} />
          ) : (
            <ArrowDownToLine size={28} />
          )}
        </div>
        <p className="eyebrow">Calix {state.current}</p>
        <h2>{state.message}</h2>
        {state.latest && (
          <p className="muted">{state.latest.replace(/^v/, "")}</p>
        )}
      </div>
      {state.phase === "downloading" && (
        <div className="update-progress">
          <progress max={100} value={state.progress || 0} />
          <span>{state.progress || 0}%</span>
        </div>
      )}
      <div className="dialog-actions">
        <button
          className="quiet"
          onClick={() =>
            void rpc("app.open", { page: "releases" }).catch((error) =>
              notify(error.message),
            )
          }
        >
          릴리즈 <ArrowUpRight size={15} />
        </button>
        <span />
        {!working && state.phase !== "ready" && (
          <button
            onClick={() =>
              void rpc("update.check").catch((error) => notify(error.message))
            }
          >
            <RefreshCw size={15} />
            다시 확인
          </button>
        )}
        {state.phase === "available" && (
          <button
            className="primary"
            onClick={() =>
              void rpc("update.download").catch((error) =>
                notify(error.message),
              )
            }
          >
            <ArrowDownToLine size={16} />
            다운로드
          </button>
        )}
        {state.phase === "ready" && (
          <button
            className="primary"
            onClick={() => {
              keep.current = true;
              onInstall();
            }}
          >
            설치하고 종료
          </button>
        )}
      </div>
    </Modal>
  );
}
