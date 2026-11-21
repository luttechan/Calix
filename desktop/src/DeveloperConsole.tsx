import { useCallback, useEffect, useRef, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { Modal } from "./App";
import { ConsoleView, type ConsoleAction, type ConsoleState, type LogRow } from "./ConsoleView";
import { rpc, subscribe } from "./bridge";

const CAPACITY = 600;

function errorMessage(error: unknown) {
  return error instanceof Error ? `${error.name}: ${error.message}`.slice(0, 500) : "Unhandled interface error";
}

export function DeveloperConsole({ allowed, onError, onOpenError }: {
  allowed: boolean;
  onError: () => void;
  onOpenError: () => void;
}) {
  const native = isTauri();
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [rows, setRows] = useState<LogRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [force, setForce] = useState(false);
  const [error, setError] = useState("");
  const [ready, announceReady] = useState(0);
  const after = useRef(0);
  const localSequence = useRef(0);
  const capture = useRef(false);
  const revision = useRef(0);
  const operations = useRef<Promise<unknown>>(Promise.resolve());
  const nativeOperations = useRef<Promise<unknown>>(Promise.resolve());

  const setLogging = useCallback((value: boolean) => {
    revision.current++;
    capture.current = value;
    const gen = revision.current;
    const request = operations.current.then(async () => {
      if (gen !== revision.current) return;
      const result = await rpc<boolean>("diagnostics.enable", { enabled: value });
      if (gen !== revision.current) return;
      setEnabled(result);
      capture.current = result;
      if (value) {
        after.current = 0;
        setRows([]);
      }
    });
    operations.current = request.catch(() => {});
    return request;
  }, []);

  const setNativeOpen = useCallback((value: boolean) => {
    const request = nativeOperations.current.then(() => invoke("developer_console", { open: value }));
    nativeOperations.current = request.catch(() => {});
    return request;
  }, []);

  useEffect(() => {
    if (open && error) onError();
  }, [error, onError, open]);

  useEffect(() => {
    if (!allowed) {
      setOpen(false);
      if (native) void invoke("developer_disable").catch(() => {});
      return;
    }
    const show = () => setOpen(true);
    const key = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && !event.altKey && !event.repeat && event.code === "KeyD") {
        event.preventDefault();
        event.stopImmediatePropagation();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", key, true);
    window.addEventListener("calix:developer-console", show);
    return () => {
      window.removeEventListener("keydown", key, true);
      window.removeEventListener("calix:developer-console", show);
    };
  }, [allowed, native]);

  useEffect(() => {
    if (!open || !allowed) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      let next = 450;
      const gen = revision.current;
      try {
        const update = await rpc<{ enabled: boolean; rows: LogRow[] }>(
          "diagnostics.read", { after: after.current },
        );
        if (active && gen === revision.current) {
          setEnabled(update.enabled);
          if (update.rows.length) {
            after.current = update.rows[update.rows.length - 1].id;
            setRows((previous) => [...previous, ...update.rows].slice(-CAPACITY));
          }
        }
      } catch {
        next = 1500;
      }
      if (active) timer = setTimeout(poll, next);
    };
    const boot = async () => {
      try {
        if (native) await setNativeOpen(true);
        if (!active) return;
      } catch {
        if (active) {
          setOpen(false);
          onOpenError();
        }
        return;
      }
      try {
        await setLogging(true);
      } catch {
        if (active) setError("Unable to start log capture.");
      }
      if (!active) return;
      void rpc<{ busy: boolean }>("engine.state").then((state) => {
        if (active) setBusy(state.busy);
      }).catch(() => {});
      void poll();
    };
    const addition = subscribe((message) => {
      if (message.event === "sync-state") setBusy(Boolean(message.busy));
    });
    const record = (event: Event) => {
      if (!active || !capture.current) return;
      if (event.type === "calix:engine-error") {
        const message = (event as CustomEvent<string>).detail;
        const row: LogRow = {
          id: --localSequence.current, source: "bridge", level: "error",
          time: new Date().toISOString(), message,
        };
        setRows((previous) => [...previous, row].slice(-CAPACITY));
        return;
      }
      const message =
        event.type === "calix:ui-error" ? (event as CustomEvent<string>).detail :
        event.type === "error" ? errorMessage((event as ErrorEvent).error) :
        errorMessage((event as PromiseRejectionEvent).reason);
      void rpc("diagnostics.record", { source: "ui", level: "error", message }).catch(() => {});
    };
    window.addEventListener("error", record);
    window.addEventListener("unhandledrejection", record);
    window.addEventListener("calix:ui-error", record);
    window.addEventListener("calix:engine-error", record);
    void boot();
    return () => {
      active = false;
      clearTimeout(timer);
      addition();
      window.removeEventListener("error", record);
      window.removeEventListener("unhandledrejection", record);
      window.removeEventListener("calix:ui-error", record);
      window.removeEventListener("calix:engine-error", record);
      void setLogging(false).catch(() => {});
      after.current = 0;
      setRows([]);
      setEnabled(false);
      setRequesting(false);
      setForce(false);
      setError("");
      if (native) void setNativeOpen(false).catch(() => {});
    };
  }, [open, allowed, native, onOpenError, setLogging, setNativeOpen]);

  const act = useCallback((action: ConsoleAction) => {
    if (action === "ready") {
      announceReady((count) => count + 1);
    } else if (action === "dismiss") {
      setForce(false);
    } else if (action === "capture" || action === "pause") {
      setError("");
      void setLogging(action === "capture").catch(() => setError("Unable to change log capture."));
    } else if (!requesting) {
      setRequesting(true);
      setError("");
      const method = { cancel: "sync.cancel", force: "sync.force", sync: "sync.request" }[action];
      void rpc<{ alreadyRunning?: boolean } | boolean>(method).then((result) => {
        if (action === "sync" && typeof result === "object" && result?.alreadyRunning) setForce(true);
        else {
          setForce(false);
          setBusy(action !== "cancel");
        }
      }).catch((reason) => setError(String(reason))).finally(() => setRequesting(false));
    }
  }, [requesting, setLogging]);
  const actionHandler = useRef(act);
  useEffect(() => { actionHandler.current = act; }, [act]);

  useEffect(() => {
    if (!native || !open || !allowed) return;
    let active = true;
    const action = listen<ConsoleAction>("developer-console:action", (event) => {
      if (active) actionHandler.current(event.payload);
    });
    const closed = listen("developer-console:closed", () => { if (active) setOpen(false); });
    return () => {
      active = false;
      void action.then((off) => off()).catch(() => {});
      void closed.then((off) => off()).catch(() => {});
    };
  }, [allowed, native, open]);

  useEffect(() => {
    if (!native || !open || !allowed || !ready) return;
    const state: ConsoleState = { rows, enabled, busy, requesting, force, error };
    void invoke("developer_console_publish", { state }).catch(() => {});
  }, [allowed, busy, enabled, error, force, native, open, ready, requesting, rows]);

  if (!open || !allowed || native) return null;
  return (
    <Modal title="Developer Diagnostics" closeLabel="Close" wide onClose={() => setOpen(false)}>
      <ConsoleView state={{ rows, enabled, busy, requesting, force, error }} onAction={act} />
    </Modal>
  );
}
