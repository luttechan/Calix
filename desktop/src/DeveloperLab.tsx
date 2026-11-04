import { Activity, FlaskConical, Palette, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { rpc } from "./bridge";

const tokens = [
  ["Canvas", "--bg"], ["Surface", "--surface"], ["Accent", "--accent"],
  ["Muted", "--muted"],
] as const;

export function DeveloperLab() {
  const request = useRef(0);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  useEffect(() => () => { request.current++; }, []);

  async function measure() {
    const id = ++request.current;
    setRunning(true);
    setResult(null);
    try {
      const samples: number[] = [];
      for (let index = 0; index < 5; index++) {
        const start = performance.now();
        await rpc("diagnostics.metrics");
        if (id !== request.current) return;
        samples.push(performance.now() - start);
      }
      samples.sort((a, b) => a - b);
      setResult(`Median ${samples[2].toFixed(1)} ms · Max ${samples[4].toFixed(1)} ms`);
    } catch {
      if (id === request.current) setResult("Engine unavailable.");
    } finally {
      if (id === request.current) setRunning(false);
    }
  }

  return (
    <section className="dev-lab" aria-labelledby="dev-lab-title">
      <header>
        <span className="dev-lab-icon"><FlaskConical size={19} aria-hidden="true" /></span>
        <div><p className="eyebrow">Experimental</p><h3 id="dev-lab-title">Lab</h3></div>
      </header>
      <div className="dev-lab-grid">
        <article>
          <h4><Activity size={16} aria-hidden="true" /> Engine latency</h4>
          <p>Five local round trips.</p>
          <button type="button" className="dev-lab-action" disabled={running} onClick={() => void measure()}>
            <Zap size={14} aria-hidden="true" /> {running ? "Sampling…" : "Measure"}
          </button>
          {result && <output className="dev-lab-result" aria-live="polite">{result}</output>}
        </article>
        <article>
          <h4><Palette size={16} aria-hidden="true" /> Theme palette</h4>
          <p>Live colors from the active theme.</p>
          <ul className="dev-lab-palette">
            {tokens.map(([name, token]) => (
              <li key={token}>
                <span style={{ backgroundColor: `var(${token})` }} aria-hidden="true" />
                {name}
              </li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
}
