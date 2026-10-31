import { useEffect, useRef, useState } from "react";
import { Modal } from "./App";
import { rpc } from "./bridge";

type Row = { id: number; time: string; message: string };

export function DeveloperConsole() {
  const [open, setOpen] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const after = useRef(0);
  const revision = useRef(0);
  const operations = useRef<Promise<unknown>>(Promise.resolve());
  const setLogging = (value: boolean) => {
    const request = operations.current.then(() =>
      rpc<boolean>("diagnostics.enable", { enabled: value }),
    );
    operations.current = request.catch(() => {});
    return request;
  };
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.code === "KeyD") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  useEffect(() => {
    if (!open) {
      revision.current++;
      void setLogging(false).catch(() => {});
      setEnabled(false);
      setRows([]);
      after.current = 0;
      return;
    }
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const generation = revision.current;
      try {
        const result = await rpc<{ enabled: boolean; rows: Row[] }>(
          "diagnostics.read",
          { after: after.current },
        );
        if (!active) return;
        if (generation !== revision.current) {
          timer = setTimeout(poll, 500);
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
      if (active) timer = setTimeout(poll, 500);
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
      void setLogging(false).catch(() => {});
    };
  }, [open]);
  if (!open) return null;
  return (
    <Modal title="개발자 콘솔" wide onClose={() => setOpen(false)}>
      <div className="dialog-actions">
        <label>
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
                  setError(e.message);
                });
            }}
          />{" "}
          수집 로그
        </label>
        <button
          disabled={!enabled}
          onClick={() => {
            void rpc("sync").catch((e) => setError(e.message));
          }}
        >
          동기화
        </button>
        <small>닫으면 수집을 중지하고 기록을 지웁니다.</small>
      </div>
      {error && <p role="alert">{error}</p>}
      <pre
        aria-label="크롤링 로그"
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
          .join("\n") || "기록 없음"}
      </pre>
    </Modal>
  );
}
