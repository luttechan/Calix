import { useEffect, useRef, useState } from "react";
import { isTauri, invoke } from "@tauri-apps/api/core";
import { Modal } from "./App";
import { rpc, subscribe } from "./bridge";
type Row = { id: number; time: string; message: string };
export function DeveloperConsole({ allowed }: { allowed: boolean }) {
  const [open, setOpen] = useState(false),
    [enabled, setEnabled] = useState(false),
    [rows, setRows] = useState<Row[]>([]),
    [error, setError] = useState("");
  const [busy, setBusy] = useState(false),
    [requesting, setRequesting] = useState(false),
    [force, setForce] = useState(false);
  const priority = useRef<Promise<unknown>>(Promise.resolve());
  const prioritize = (value: boolean) => {
    priority.current = priority.current
      .catch(() => {})
      .then(() => invoke("developer_console", { open: value }));
    return priority.current;
  };
  const after = useRef(0),
    revision = useRef(0),
    operations = useRef<Promise<unknown>>(Promise.resolve());
  const setLogging = (value: boolean) => {
    const request = operations.current.then(() =>
      rpc<boolean>("diagnostics.enable", { enabled: value }),
    );
    operations.current = request.catch(() => {});
    return request;
  };
  useEffect(
    () =>
      subscribe((message) => {
        if (message.event === "sync-state") setBusy(Boolean(message.busy));
      }),
    [],
  );
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (
        allowed &&
        event.ctrlKey &&
        event.shiftKey &&
        !event.altKey &&
        !event.repeat &&
        (event.code === "KeyD" ||
          event.key.toLowerCase() === "d" ||
          event.keyCode === 68)
      ) {
        event.preventDefault();
        event.stopImmediatePropagation();
        setOpen((value) => !value);
      }
    };
    const show = () => {
      if (!allowed) return;
      setOpen(true);
      void setLogging(true).catch(() =>
        setError("Unable to enable log capture."),
      );
    };
    window.addEventListener("keydown", key, true);
    window.addEventListener("calix:developer-console", show);
    return () => {
      window.removeEventListener("keydown", key, true);
      window.removeEventListener("calix:developer-console", show);
    };
  }, [allowed]);
  useEffect(() => {
    if (!allowed) {
      setOpen(false);
      if (isTauri()) void invoke("developer_disable").catch(() => {});
    }
  }, [allowed]);
  useEffect(() => {
    if (isTauri())
      void prioritize(open).catch((e) => {
        if (open) setError(String(e));
      });
    if (!open) {
      revision.current++;
      setForce(false);
      void setLogging(false).catch(() => {});
      setEnabled(false);
      setRows([]);
      after.current = 0;
      return;
    }
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    void rpc<{ busy: boolean }>("engine.state")
      .then((value) => {
        if (active) setBusy(value.busy);
      })
      .catch(() => {});
    const poll = async () => {
      const generation = revision.current;
      try {
        const result = await rpc<{ enabled: boolean; rows: Row[] }>(
          "diagnostics.read",
          { after: after.current },
        );
        if (!active) return;
        if (generation !== revision.current) {
          timer = setTimeout(poll, 300);
          return;
        }
        setEnabled(result.enabled);
        if (result.rows.length) {
          after.current = result.rows[result.rows.length - 1].id;
          setRows((previous) => [...previous, ...result.rows].slice(-600));
        }
      } catch (e) {
        if (active) setError(String(e));
      }
      if (active) timer = setTimeout(poll, 300);
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
      void setLogging(false).catch(() => {});
      if (isTauri()) void prioritize(false).catch(() => {});
    };
  }, [open]);
  const requestSync = async (forceRun = false) => {
    if (requesting) return;
    setRequesting(true);
    setError("");
    try {
      if (forceRun) {
        await rpc("sync.force");
        setForce(false);
        setBusy(true);
      } else {
        const result = await rpc<{ alreadyRunning: boolean }>("sync.request");
        if (result.alreadyRunning) setForce(true);
        else setBusy(true);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRequesting(false);
    }
  };
  if (!open || !allowed) return null;
  return (
    <>
      <Modal
        title="Live Console"
        closeLabel="Close"
        wide
        onClose={() => setOpen(false)}
      >
        <div className="dialog-actions developer-actions">
          <label className="developer-log-toggle">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => {
                const value = event.target.checked;
                revision.current++;
                setEnabled(value);
                const generation = revision.current;
                void setLogging(value)
                  .then((result) => {
                    if (generation !== revision.current) return;
                    setEnabled(result);
                    setRows([]);
                    after.current = 0;
                    setError("");
                  })
                  .catch((e) => {
                    if (generation !== revision.current) return;
                    setEnabled(!value);
                    setError(String(e));
                  });
              }}
            />
            Capture logs
          </label>
          <button disabled={requesting} onClick={() => void requestSync()}>
            Sync
          </button>
          <button
            disabled={!busy || requesting}
            onClick={() => {
              setRequesting(true);
              void rpc("sync.cancel")
                .catch((e) => setError(String(e)))
                .finally(() => setRequesting(false));
            }}
          >
            Cancel Sync
          </button>
          <small>{busy ? "Collector running" : "Collector idle"}</small>
        </div>
        {error && <p role="alert">{error}</p>}
        <pre
          aria-label="Live logs"
          style={{
            background: "#111218",
            color: "#d8e8dc",
            padding: 16,
            borderRadius: 16,
            height: "min(55vh, 480px)",
            overflow: "auto",
            whiteSpace: "pre-wrap",
            overflowWrap: "anywhere",
            fontSize: 12,
            userSelect: "text",
          }}
        >
          {rows
            .map((row) => `[${row.time.slice(11)}] ${row.message}`)
            .join("\n") || "No logs captured"}
        </pre>
      </Modal>
      {force && (
        <Modal
          title="Force Synchronizing?"
          closeLabel="Close"
          onClose={() => {
            if (!requesting) setForce(false);
          }}
        >
          <p>A synchronization job is already running.</p>
          <p className="muted">
            Abort the active run and restart the collector with a new run_id?
          </p>
          <div className="dialog-actions">
            <span />
            <button disabled={requesting} onClick={() => setForce(false)}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={requesting}
              onClick={() => void requestSync(true)}
            >
              Force Synchronizing
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
