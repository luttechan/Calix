import { Activity, FlaskConical, Palette, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Modal, useCalix } from "./App";
import { rpc } from "./bridge";
import { paletteTokens, paletteValues, validPaletteColor } from "./themePalette";
import type { PaletteColor, ThemePalette } from "./types";

export function DeveloperLab() {
  const { data, mutate, notify, soundError } = useCalix();
  const request = useRef(0);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ initial: Record<PaletteColor, string>; colors: Record<PaletteColor, string> } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  useEffect(() => () => { request.current++; }, []);

  async function savePalette(colors: ThemePalette) {
    setSaving(true);
    setSaveError("");
    try {
      await mutate("preferences.palette.save", { theme: data.preferences.theme, colors });
      setEditor(null);
      notify("Palette saved.");
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  }

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
      if (id === request.current) {
        setResult("Engine unavailable.");
        soundError();
      }
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
          <ul className="dev-lab-palette">
            {paletteTokens.map(([, name, token]) => (
              <li key={token}>
                <span style={{ backgroundColor: `var(${token})` }} aria-hidden="true" />
                {name}
              </li>
            ))}
          </ul>
          <button type="button" className="dev-lab-action" onClick={() => {
            const colors = paletteValues(getComputedStyle(document.documentElement));
            setSaveError("");
            setEditor({ initial: colors, colors });
          }}>Edit colors</button>
        </article>
      </div>
      {editor && (
        <Modal title="Theme palette" closeLabel="Close" onClose={() => { if (!saving) setEditor(null); }}>
          <form onSubmit={(event) => {
            event.preventDefault();
            if (saving || !Object.values(editor.colors).every(validPaletteColor)) return;
            const overrides = { ...data.preferences.theme_palette };
            for (const [key] of paletteTokens) {
              if (editor.colors[key].toLowerCase() !== editor.initial[key].toLowerCase()) overrides[key] = editor.colors[key];
            }
            void savePalette(overrides);
          }}>
            <fieldset className="dev-palette-editor" disabled={saving}>
              {paletteTokens.map(([key, label]) => {
                const color = editor.colors[key];
                const update = (value: string) => setEditor({ ...editor, colors: { ...editor.colors, [key]: value } });
                return <div className="dev-palette-field" key={key}>
                  <label htmlFor={`palette-${key}`}>{label}</label>
                  <input type="color" id={`palette-${key}`} value={validPaletteColor(color) ? color.toLowerCase() : editor.initial[key]} onChange={(event) => update(event.target.value)} />
                  <input aria-label={`${label} hex`} value={color} spellCheck={false} required maxLength={7} pattern="#[0-9a-fA-F]{6}" onChange={(event) => update(event.target.value)} />
                </div>;
              })}
            </fieldset>
            {saveError && <p role="alert" className="danger">{saveError}</p>}
            <div className="dialog-actions">
              <button type="button" disabled={saving || !Object.keys(data.preferences.theme_palette ?? {}).length} onClick={() => void savePalette({})}>Reset defaults</button>
              <button type="submit" className="primary" disabled={saving}>Apply</button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
