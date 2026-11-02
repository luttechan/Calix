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
  const [developerMode, setDeveloperMode] = useState(
    Boolean(data.preferences.developer_mode),
  );
  useEffect(
    () => setDeveloperMode(Boolean(data.preferences.developer_mode)),
    [data.preferences.developer_mode],
  );
  useEffect(() => {
    if (!active) {
      setMonitoring(false);
      setReport(null);
      setForce(false);
    }
  }, [active]);
  useEffect(() => {
    if (!active || !monitoring) return;
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
  }, [active, monitoring]);
  const run = async (action: () => Promise<void>) => {
    if (pending) return;
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
            disabled={pending}
            onChange={(event) => {
              const value = event.target.checked;
              setDeveloperMode(value);
              void run(async () => {
                try {
                  await mutate("preferences.save", { developer_mode: value });
                } catch (error) {
                  setDeveloperMode(!value);
                  throw error;
                }
              });
            }}
          />
          Developer Mode
        </label>
      </div>
      <p className="dev-warning">
        Developer tools are not recommended for general use.
      </p>
      <div className="dev-tools">
        {tools.map(([name, description, action]) => (
          <button
            key={name}
            disabled={pending}
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
      {monitoring && (
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
      {report && active && (
        <Modal
          title="Sync Inspector"
          closeLabel="Close"
          wide
          onClose={() => setReport(null)}
        >
          <pre className="dev-report">{JSON.stringify(report, null, 2)}</pre>
        </Modal>
      )}
      {force && active && (
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
    </section>
  );
}
