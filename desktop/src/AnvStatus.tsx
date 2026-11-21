import { useEffect, useState } from "react";
import { Cable, RefreshCw } from "lucide-react";
import { rpc } from "./bridge";
import "./anki-review.css";

type AnvConnection =
  | { connected: false }
  | { connected: true; autoSync: boolean; lastSync: string; syncFailed: boolean };

export function AnvStatus() {
  const [revision, setRevision] = useState(0);
  const [status, setStatus] = useState<AnvConnection>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void rpc<AnvConnection>("anv.status")
        .then(value => { if (active) setStatus(value); })
        .catch(() => { if (active) setStatus({ connected: false }); })
        .finally(() => { if (active) setLoading(false); });
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [revision]);

  return (
    <section className="glass anki-review" aria-labelledby="anv-status-heading">
      <div className="anki-review-header">
        <h2 id="anv-status-heading"><Cable size={18} aria-hidden="true" /> ANV</h2>
        <button type="button" disabled={loading} aria-label="ANV 새로고침" onClick={() => {
          setLoading(true);
          setRevision(value => value + 1);
        }}>
          <RefreshCw size={15} aria-hidden="true" /> 새로고침
        </button>
      </div>
      <p className="muted" role="status">
        {loading ? "연결 확인 중" : status?.connected ? "연결됨" : "연결 안 됨"}
      </p>
      {status?.connected && (
        <dl className="anki-review-totals">
          <div><dt>자동 동기화</dt><dd>{status.autoSync ? "동작 중" : "중지"}</dd></div>
          <div><dt>마지막 동기화</dt><dd>{status.lastSync || "기록 없음"}</dd></div>
          {status.syncFailed && <div><dt>최근 시도</dt><dd>실패</dd></div>}
        </dl>
      )}
    </section>
  );
}
