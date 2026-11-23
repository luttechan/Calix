import { useEffect, useState } from "react";
import { Link2, QrCode, Smartphone } from "lucide-react";
import { rpc } from "./bridge";
import { t, useLanguage } from "./i18n";
import "./vesper-pairing.css";

type Preview = { expiresAt: number; rows: string[] };
type Code = { expiresAt: number; localDeadline: number; size: number; path: string };

function secondsLeft(code: Code) {
  const remaining = Math.min(code.expiresAt - Date.now(), code.localDeadline - performance.now());
  return Math.max(0, Math.ceil(remaining / 1000));
}

function prepareCode(preview: Preview): Code {
  const { expiresAt, rows } = preview;
  const size = rows.length;
  if (!Number.isSafeInteger(expiresAt) || size < 21 || size > 177 ||
      (size - 21) % 4 !== 0 || rows.some(row => row.length !== size || /[^01]/.test(row))) {
    throw new Error("Invalid pairing preview");
  }
  const parts: string[] = [];
  for (const [y, row] of rows.entries()) {
    for (let x = 0; x < size; x++) {
      if (row[x] === "1") parts.push(`M${x},${y}h1v1h-1z`);
    }
  }
  return { expiresAt, localDeadline: performance.now() + Math.min(300_000, expiresAt - Date.now()), size, path: parts.join("") };
}

export function VesperPairing() {
  useLanguage();
  const [code, setCode] = useState<Code | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [pending, setPending] = useState(false);
  const [expired, setExpired] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!code) return;
    const update = () => {
      const left = secondsLeft(code);
      setSeconds(left);
      if (left === 0) {
        setCode(null);
        setExpired(true);
      }
    };
    const timer = window.setInterval(update, 250);
    document.addEventListener("visibilitychange", update);
    window.addEventListener("focus", update);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", update);
      window.removeEventListener("focus", update);
    };
  }, [code]);

  const generate = async () => {
    setPending(true);
    setCode(null);
    setExpired(false);
    setFailed(false);
    try {
      const next = prepareCode(await rpc<Preview>("vesper.pairing.preview"));
      const left = secondsLeft(next);
      if (left === 0) setExpired(true);
      else {
        setSeconds(left);
        setCode(next);
      }
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  };
  const remaining = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <section className="glass settings-panel" aria-labelledby="vesper-pairing-title">
      <div className="settings-heading">
        <Link2 aria-hidden="true" />
        <h2 id="vesper-pairing-title">{t("기기 연동")}</h2>
      </div>
      <div className="vesper-pairing-card">
        <div className="vesper-pairing-copy">
          <div className="vesper-pairing-product">
            <span className="vesper-pairing-icon" aria-hidden="true"><Smartphone size={23} /></span>
            <div><h3>Calix Vesper</h3><span>iPhone</span></div>
          </div>
          <p className="vesper-pairing-status">{t("연동 준비 중")}</p>
          <div className="vesper-pairing-actions">
            <button type="button" className="primary" disabled={pending} onClick={() => void generate()}>
              <QrCode size={17} aria-hidden="true" />{t(code || expired ? "QR 다시 생성" : "QR 생성")}
            </button>
            {code && <button type="button" onClick={() => setCode(null)}>{t("QR 닫기")}</button>}
          </div>
          {expired && <p role="status">{t("QR이 만료되었습니다.")}</p>}
          {failed && <p className="danger" role="alert">{t("QR을 생성하지 못했습니다.")}</p>}
        </div>
        {code && (
          <figure className="vesper-pairing-code">
            <svg role="img" aria-label={t("Vesper 연동 준비용 QR")} viewBox={`-4 -4 ${code.size + 8} ${code.size + 8}`} shapeRendering="crispEdges">
              <rect x="-4" y="-4" width={code.size + 8} height={code.size + 8} fill="#fff" />
              <path d={code.path} fill="#000" />
            </svg>
            <figcaption><span>{t("남은 유효 시간")}</span><span role="timer">{remaining}</span></figcaption>
          </figure>
        )}
      </div>
    </section>
  );
}
