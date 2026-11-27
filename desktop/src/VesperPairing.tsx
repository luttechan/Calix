import { useEffect, useRef, useState } from "react";
import { Check, Clipboard, Link2, QrCode, Smartphone } from "lucide-react";
import { useCalix } from "./App";
import { rpc } from "./bridge";
import { t, useLanguage } from "./i18n";
import "./vesper-pairing.css";

type Preview = { expiresAt: number; rows: string[]; uri: string };
type Code = { expiresAt: number; localDeadline: number; size: number; path: string; uri: string };
type Status = { phase: "closed" | "waiting" | "approval" | "complete"; name?: string; code?: string; conflicts?: number };

function secondsLeft(code: Code) {
  const remaining = Math.min(code.expiresAt - Date.now(), code.localDeadline - performance.now());
  return Math.max(0, Math.ceil(remaining / 1000));
}

function prepareCode(preview: Preview): Code {
  const { expiresAt, rows, uri } = preview;
  const size = rows.length;
  if (!uri.startsWith("calix-vesper://pair?v=3&") || !Number.isSafeInteger(expiresAt) || size < 21 || size > 177 ||
      (size - 21) % 4 !== 0 || rows.some(row => row.length !== size || /[^01]/.test(row))) {
    throw new Error("Invalid pairing code");
  }
  const parts: string[] = [];
  for (const [y, row] of rows.entries()) {
    for (let x = 0; x < size; x++) {
      if (row[x] === "1") parts.push(`M${x},${y}h1v1h-1z`);
    }
  }
  return { expiresAt, localDeadline: performance.now() + Math.min(300_000, expiresAt - Date.now()), size, path: parts.join(""), uri };
}

export function VesperPairing() {
  useLanguage();
  const { mutate } = useCalix();
  const [interfaces, setInterfaces] = useState<string[]>([]);
  const [host, setHost] = useState("");
  const [code, setCode] = useState<Code | null>(null);
  const [seconds, setSeconds] = useState(0);
  const [pending, setPending] = useState(false);
  const [expired, setExpired] = useState(false);
  const [failed, setFailed] = useState<"code" | "approval" | null>(null);
  const [showLink, setShowLink] = useState(false);
  const [status, setStatus] = useState<Status>({ phase: "closed" });
  const request = useRef(0);

  useEffect(() => {
    let active = true;
    void rpc<string[]>("vesper.transfer.addresses").then(list => { if (active) setInterfaces(list); }).catch(() => {});
    return () => {
      active = false;
      request.current++;
      void rpc("vesper.transfer.close").catch(() => {});
    };
  }, []);

  useEffect(() => {
    if (!code || status.phase === "complete") return;
    let open = true;
    let polling = false;
    const update = () => {
      const left = secondsLeft(code);
      setSeconds(left);
      if (left === 0) {
        void rpc("vesper.transfer.close").catch(() => {});
        setCode(null);
        setStatus({ phase: "closed" });
        setExpired(true);
      }
    };
    const poll = () => {
      update();
      if (polling || secondsLeft(code) === 0) return;
      polling = true;
      void rpc<Status>("vesper.transfer.status").then(next => {
        if (open) setStatus(previous => previous.phase === "complete" ? previous : next);
      }).catch(() => {}).finally(() => { polling = false; });
    };
    const timer = window.setInterval(poll, 1000);
    document.addEventListener("visibilitychange", update);
    window.addEventListener("focus", update);
    return () => {
      open = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", update);
      window.removeEventListener("focus", update);
    };
  }, [code, status.phase]);

  const generate = async () => {
    const current = ++request.current;
    setPending(true);
    setCode(null);
    setExpired(false);
    setFailed(null);
    setShowLink(false);
    try {
      const next = prepareCode(await rpc<Preview>("vesper.transfer.start", { host }));
      if (current !== request.current) return;
      const left = secondsLeft(next);
      if (left === 0) setExpired(true);
      else {
        setSeconds(left);
        setCode(next);
        setStatus({ phase: "waiting" });
      }
    } catch {
      if (current === request.current) setFailed("code");
    } finally {
      if (current === request.current) setPending(false);
    }
  };
  const close = () => {
    request.current++;
    setCode(null);
    setStatus({ phase: "closed" });
    setShowLink(false);
    setPending(false);
    setFailed(null);
    void rpc("vesper.transfer.close").catch(() => {});
  };
  const approve = async () => {
    setPending(true);
    setFailed(null);
    try {
      const next = await mutate("vesper.transfer.approve") as Status;
      setCode(null);
      setStatus(next);
    } catch {
      setFailed("approval");
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
          <p className="vesper-pairing-status">{t("같은 Wi-Fi에서 Vesper와 연결하세요.")}</p>
          {interfaces.length > 1 && <label>{t("네트워크 주소")}
            <select value={host || interfaces[0]} disabled={!!code || pending} onChange={event => setHost(event.target.value)}>
              {interfaces.map(address => <option key={address}>{address}</option>)}
            </select>
          </label>}
          {status.phase === "approval" && <div className="vesper-pairing-approval">
            <span>{status.name}</span>
            <strong>{status.code}</strong>
            <p>{t("iPhone의 확인 코드와 같으면 승인하세요.")}</p>
          </div>}
          {status.phase === "complete" && <p className="vesper-pairing-result" role="status">
            <Check size={16} aria-hidden="true" />{t("연동 완료")}
            {status.conflicts ? <span>{t("양쪽에서 수정된 항목 {0}개를 각각 보존했습니다.", [status.conflicts])}</span> : null}
          </p>}
          <div className="vesper-pairing-actions">
            {status.phase === "approval" ? <button type="button" className="primary" disabled={pending}
              onClick={() => void approve().catch(() => {})}>{t("연동 승인")}</button> :
              <button type="button" className="primary" disabled={pending} onClick={() => void generate()}>
                <QrCode size={17} aria-hidden="true" />{t(code || expired ? "QR 다시 생성" : "QR 생성")}
              </button>}
            {code && <button type="button" disabled={pending} onClick={close}>{t("QR 닫기")}</button>}
            {code && status.phase === "waiting" && <button type="button" onClick={() => {
              void navigator.clipboard?.writeText(code.uri).catch(() => setShowLink(true));
              if (!navigator.clipboard) setShowLink(true);
            }}><Clipboard size={15} aria-hidden="true" />{t("연동 주소 복사")}</button>}
          </div>
          {code && showLink && <input readOnly aria-label={t("연동 주소")} value={code.uri} onFocus={event => event.currentTarget.select()} />}
          {expired && <p role="status">{t("QR이 만료되었습니다.")}</p>}
          {failed && <p className="danger" role="alert">{t(failed === "approval" ? "연동을 완료하지 못했습니다." : "QR을 생성하지 못했습니다.")}</p>}
        </div>
        {code && status.phase === "waiting" && (
          <figure className="vesper-pairing-code">
            <svg role="img" aria-label={t("Vesper 연동 QR")} viewBox={`-4 -4 ${code.size + 8} ${code.size + 8}`} shapeRendering="crispEdges">
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
