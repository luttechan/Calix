import { useEffect, useState } from "react";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { Modal, useCalix } from "./App";
import { rpc } from "./bridge";

type Metrics = { rss_mb: number; uptime_seconds: number };
export function DevPanel({ active }: { active: boolean }) {
  const { data, mutate } = useCalix();
  const [monitoring, setMonitoring] = useState(false);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [report, setReport] = useState<object | null>(null);
  const [force, setForce] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [fps, setFps] = useState(0);
  const [enableWarning, setEnableWarning] = useState(false);
  const [operation, setOperation] = useState<string | null>(null);
  const [maintenance, setMaintenance] = useState(false);
  const unlocked = Boolean(data.preferences.developer_mode);
  const [developerMode, setDeveloperMode] = useState(
    Boolean(data.preferences.developer_mode),
  );
  useEffect(
    () => setDeveloperMode(Boolean(data.preferences.developer_mode)),
    [data.preferences.developer_mode],
  );
  useEffect(() => {
    if (!active || !unlocked) {
      setMonitoring(false);
      setReport(null);
      setForce(false);
      setOperation(null);
      setEnableWarning(false);
    }
  }, [active, unlocked]);
  useEffect(() => {
    if (!active || !unlocked || !monitoring) return;
    let cancelled = false,
      timer: ReturnType<typeof setTimeout>,
      frame = 0;
    let start = performance.now(),
      frames = 0;
    const tick = (now: number) => {
      frames++;
      if (now - start >= 1000) {
        setFps(Math.round((frames * 1000) / (now - start)));
        frames = 0;
        start = now;
      }
      frame = requestAnimationFrame(tick);
    };
    const poll = async () => {
      try {
        const value = await rpc<Metrics>("diagnostics.metrics");
        if (!cancelled) setMetrics(value);
      } catch {
        if (!cancelled) setMessage("Performance metrics unavailable.");
      }
      if (!cancelled) timer = setTimeout(poll, 2000);
    };
    frame = requestAnimationFrame(tick);
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      cancelAnimationFrame(frame);
    };
  }, [active, unlocked, monitoring]);
  useEffect(() => {
    if (!active || !unlocked) return;
    let cancelled = false,
      timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const state = await rpc<{
          phase: string;
          report?: object;
          message?: string;
        }>("developer.maintenance.state");
        if (cancelled) return;
        setMaintenance(state.phase === "working");
        if (state.phase === "working") timer = setTimeout(poll, 400);
        else if (state.phase === "complete" && state.report && maintenance) {
          setReport(state.report);
          setMessage("Maintenance completed. Review the report.");
        } else if (state.phase === "error")
          setMessage(state.message || "Maintenance failed.");
      } catch {
        if (!cancelled) setMaintenance(false);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [active, unlocked, maintenance]);
  const applyMode = async (value: boolean) => {
    setPending(true);
    setMessage("");
    try {
      await mutate("preferences.save", {
        developer_mode: value,
        developer_acknowledged: value,
      });
      setDeveloperMode(value);
      setEnableWarning(false);
    } catch {
      setMessage("Unable to change Developer Mode.");
    } finally {
      setPending(false);
    }
  };
  const run = async (action: () => Promise<void>) => {
    if (pending || maintenance || !unlocked) return;
    setPending(true);
    setMessage("");
    try {
      await action();
    } catch {
      setMessage("Operation failed. Open Live Console for details.");
    } finally {
      setPending(false);
    }
  };
  const tools = [
    [
      "Live Console",
      "Inspect runtime events and collector logs.",
      () => window.dispatchEvent(new Event("calix:developer-console")),
    ],
    [
      "WebView DevTools",
      "Inspect the interface, network and JavaScript console.",
      () =>
        void run(async () => {
          if (!isTauri()) {
            setMessage("Available in the Windows app.");
            return;
          }
          await invoke("developer_devtools");
        }),
    ],
    [
      "Sync Inspector",
      "View local collection state without network requests.",
      () =>
        void run(async () =>
          setReport(await rpc<object>("diagnostics.snapshot")),
        ),
    ],
    [
      "Force Sync",
      "Abort the active run and start a fresh collector run.",
      () => setForce(true),
    ],
    [
      "Performance Monitor",
      "Sample engine memory and interface frame rate.",
      () => setMonitoring((value) => !value),
    ],
    [
      "Export Diagnostics",
      "Save runtime state and captured logs. Credentials are excluded.",
      () =>
        void run(async () => {
          const result = await rpc<object>("diagnostics.snapshot");
          if (!isTauri()) {
            setMessage("Available in the Windows app.");
            return;
          }
          const saved = await invoke<boolean>("developer_export", {
            report: result,
          });
          if (saved) setMessage("Diagnostics exported.");
        }),
    ],
    [
      "Check Database",
      "Check SQLite integrity and foreign keys.",
      () => setOperation("integrity"),
    ],
    [
      "Reset Sync Cache",
      "Discard content fingerprints and recheck courses on the next sync.",
      () => setOperation("clear_sync_cache"),
    ],
    [
      "Optimize Database",
      "Update SQLite query plans. A recovery copy is saved first.",
      () => setOperation("optimize"),
    ],
  ] as const;
  return (
    <section className="dev-panel" lang="en">
      <div className="dev-heading">
        <div>
          <p className="eyebrow">Developer tools</p>
          <h2>Dev</h2>
        </div>
        <label className="dev-mode">
          <input
            type="checkbox"
            checked={developerMode}
            disabled={pending || maintenance}
            onChange={(event) => {
              const value = event.target.checked;
              if (value) setEnableWarning(true);
              else void applyMode(false);
            }}
          />
          Developer Mode
        </label>
      </div>
      <p className="dev-warning">
        Developer tools can cause critical errors, data loss, or an unusable
        database. Not recommended for general use.
      </p>
      {unlocked && (
        <div className="dev-tools">
          {tools.map(([name, description, action]) => (
            <button
              key={name}
              disabled={pending || maintenance}
              onClick={action}
              aria-pressed={
                name === "Performance Monitor" ? monitoring : undefined
              }
            >
              <strong>
                {name}
                {name === "Performance Monitor" && monitoring ? " / Live" : ""}
              </strong>
              <span>{description}</span>
              <b aria-hidden="true">↗</b>
            </button>
          ))}
        </div>
      )}
      {unlocked && maintenance && (
        <p role="status">Database maintenance is running…</p>
      )}
      {unlocked && monitoring && (
        <output className="dev-metrics">
          <span>
            Engine RSS{" "}
            <b>{metrics ? `${metrics.rss_mb.toFixed(1)} MB` : "Sampling…"}</b>
          </span>
          <span>
            Interface <b>{fps} FPS</b>
          </span>
          <span>
            Engine uptime{" "}
            <b>{metrics ? `${Math.floor(metrics.uptime_seconds)} s` : "—"}</b>
          </span>
        </output>
      )}
      {message && <p role="status">{message}</p>}
      {unlocked && report && active && (
        <Modal
          title={"action" in report ? "Maintenance Report" : "Sync Inspector"}
          closeLabel="Close"
          wide
          onClose={() => setReport(null)}
        >
          <pre className="dev-report">{JSON.stringify(report, null, 2)}</pre>
        </Modal>
      )}
      {unlocked && force && active && (
        <Modal
          title="Force Synchronizing?"
          closeLabel="Close"
          onClose={() => setForce(false)}
        >
          <p>
            Abort the active synchronization and restart the collector with a
            new run_id?
          </p>
          <div className="dialog-actions">
            <span />
            <button onClick={() => setForce(false)}>Cancel</button>
            <button
              className="primary"
              disabled={pending}
              onClick={() =>
                void run(async () => {
                  await rpc("sync.force");
                  setForce(false);
                  setMessage("Collector restart requested.");
                })
              }
            >
              Force Synchronizing
            </button>
          </div>
        </Modal>
      )}
      {enableWarning && active && (
        <Modal
          title="Enable Developer Mode?"
          closeLabel="Close"
          onClose={() => setEnableWarning(false)}
        >
          <p>
            Developer tools can cause critical errors, data loss, or an unusable
            database.
          </p>
          <p className="muted">Enable only if you understand these risks.</p>
          <div className="dialog-actions">
            <span />
            <button disabled={pending} onClick={() => setEnableWarning(false)}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={pending}
              onClick={() => void applyMode(true)}
            >
              Enable Developer Mode
            </button>
          </div>
        </Modal>
      )}
      {unlocked && operation && active && (
        <Modal
          title="Run Database Maintenance?"
          closeLabel="Close"
          onClose={() => setOperation(null)}
        >
          <p>
            {operation === "integrity"
              ? "Run a read-only integrity check on the active learning database?"
              : operation === "clear_sync_cache"
                ? "Reset content fingerprints? Courses will be checked again on the next sync."
                : "Update the active database's SQLite query plans?"}
          </p>
          {operation !== "integrity" && (
            <p className="dev-warning">
              Internal data will change. A recovery copy is saved first. Do not
              interrupt the operation.
            </p>
          )}
          <div className="dialog-actions">
            <span />
            <button disabled={pending} onClick={() => setOperation(null)}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={pending}
              onClick={() =>
                void run(async () => {
                  await rpc("developer.maintenance.start", {
                    action: operation,
                    confirmed: true,
                  });
                  setReport(null);
                  setOperation(null);
                  setMaintenance(true);
                })
              }
            >
              Run Maintenance
            </button>
          </div>
        </Modal>
      )}
    </section>
  );
}
