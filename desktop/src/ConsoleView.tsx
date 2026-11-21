import { useEffect, useRef, useState } from "react";
import { CirclePause, Play, Search, Terminal } from "lucide-react";
import "./console.css";

export type LogRow = {
  id: number;
  time: string;
  source: "engine" | "sync" | "ui" | "bridge";
  level: "info" | "warn" | "error";
  message: string;
};
export type ConsoleState = {
  rows: LogRow[];
  enabled: boolean;
  busy: boolean;
  requesting: boolean;
  force: boolean;
  error: string;
};
export type ConsoleAction = "ready" | "sync" | "force" | "dismiss" | "cancel" | "capture" | "pause";
export const emptyConsole: ConsoleState = { rows: [], enabled: false, busy: false, requesting: false, force: false, error: "" };

export function ConsoleView({
  state,
  onAction,
}: {
  state: ConsoleState;
  onAction: (action: ConsoleAction) => void;
}) {
  const [filter, setFilter] = useState("");
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [follow, setFollow] = useState(true);
  const list = useRef<HTMLDivElement>(null);
  const query = filter.trim().toLowerCase();
  const visible = state.rows.filter((row) =>
    (!onlyIssues || (row.level ?? "info") !== "info") &&
    (!query || `${row.source ?? "engine"} ${row.level ?? "info"} ${row.message}`.toLowerCase().includes(query)),
  );
  useEffect(() => {
    if (follow && list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [state.rows, filter, onlyIssues, follow]);
  return (
    <section className="console-view" aria-label="Calix Console" lang="en">
      <header className="console-heading">
        <h1><Terminal size={19} aria-hidden="true" /> Calix Console</h1>
        <span className="console-status" data-live={state.enabled}>{state.enabled ? "Capturing" : "Paused"}</span>
      </header>
      <div className="console-toolbar">
        <button type="button" onClick={() => onAction(state.enabled ? "pause" : "capture")}>
          {state.enabled ? <CirclePause size={15} /> : <Play size={15} />}
          {state.enabled ? "Pause" : "Capture"}
        </button>
        <button type="button" disabled={state.requesting} onClick={() => onAction("sync")}>Sync</button>
        <button type="button" disabled={!state.busy || state.requesting} onClick={() => onAction("cancel")}>Cancel Sync</button>
        <label className="console-search">
          <Search size={15} aria-hidden="true" />
          <input aria-label="Filter logs" placeholder="Filter logs" value={filter} onChange={(event) => setFilter(event.target.value)} />
        </label>
        <button type="button" aria-pressed={onlyIssues} onClick={() => setOnlyIssues(!onlyIssues)}>Issues only</button>
        <button type="button" aria-pressed={follow} onClick={() => setFollow(!follow)}>Follow</button>
      </div>
      {(state.force || state.error) && <div className="console-notices">
      {state.force && (
        <div className="console-prompt" role="alert">
          <span>A synchronization is already running.</span>
          <button type="button" disabled={state.requesting} onClick={() => onAction("dismiss")}>Cancel</button>
          <button type="button" disabled={state.requesting} onClick={() => onAction("force")}>Force Synchronizing</button>
        </div>
      )}
      {state.error && <div className="console-prompt" role="status">{state.error}</div>}
      </div>}
      <div className="console-logs" ref={list} aria-label="Runtime logs" tabIndex={0}>
        {visible.length === 0 && <p>{state.rows.length ? "No matching entries" : "No logs captured"}</p>}
        {visible.map((row) => (
          <div key={row.id} className="console-line" data-level={row.level ?? "info"}>
            <time dateTime={row.time}>{new Date(row.time).toLocaleTimeString("en-GB", { hour12: false })}</time>
            <span>{(row.source ?? "engine").toUpperCase()}</span>
            <span>{(row.level ?? "info").toUpperCase()}</span>
            <span>{row.message}</span>
          </div>
        ))}
      </div>
      <footer className="console-footer">
        <span>{visible.length} / {state.rows.length} entries</span>
        <span>{state.busy ? "Sync running" : "Sync idle"}</span>
      </footer>
    </section>
  );
}
