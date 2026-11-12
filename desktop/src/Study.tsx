import { NumberField } from "./NumberField";
import { useEffect, useState, useSyncExternalStore } from "react";
import { Pause, Play, RotateCcw, Settings, SkipForward, Timer, X } from "lucide-react";
import { rpc, subscribe } from "./bridge";
import { Modal, useCalix } from "./App";
import { dateKey } from "./dates";
import { DEFAULT_FOCUS_COMMENTS, focusSeconds, timerText, type FocusComments, type FocusState } from "./focusState";
import type { EventItem } from "./types";

let current: FocusState | null = null,
  readAt = 0;
const watchers = new Set<() => void>();
const watch = (f: () => void) => {
  watchers.add(f);
  return () => {
    watchers.delete(f);
  };
};
const publish = (s: FocusState) => {
  current = s;
  readAt = performance.now();
  for (const f of watchers) f();
};
let request = 0;
let notifiedSession = "";
async function read() {
  const id = ++request;
  const s = await rpc<FocusState>("focus.state");
  if (id === request) publish(s);
}
async function command(action: string, extra: Record<string, unknown> = {}) {
  ++request;
  publish(await rpc<FocusState>("focus.command", { action, ...extra }));
}
function useFocus() {
  return useSyncExternalStore(watch, () => current);
}
function Tomato() {
  return (
    <svg
      className="tomato"
      viewBox="0 0 120 112"
      role="img"
      aria-label="토마토"
    >
      <defs>
        <radialGradient id="tomatoGlow" cx="35%" cy="30%">
          <stop stopColor="#ff927f" />
          <stop offset="1" stopColor="#e44458" />
        </radialGradient>
      </defs>
      <path
        d="M60 34C26 9 0 50 15 82c12 25 34 23 45 20 12 3 36 4 46-21 15-33-12-72-46-47"
        fill="url(#tomatoGlow)"
      />
      <path
        d="M60 38 36 23l19 2L50 9l15 13 14-9-4 18 17 5-24 7Z"
        fill="#63b58b"
      />
      <path
        d="M62 27q-1-13 8-20"
        fill="none"
        stroke="#397856"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <path
        d="M28 52q-9 14-3 24"
        fill="none"
        stroke="#ffcfbd"
        strokeWidth="5"
        strokeLinecap="round"
        opacity=".7"
      />
    </svg>
  );
}
function Controls({ state }: { state: FocusState }) {
  const { notify } = useCalix();
  const run = (a: string) => void command(a).catch((e) => notify(String(e)));
  return (
    <div className="focus-controls">
      <button
        className="icon-button"
        title="세션 초기화"
        aria-label="세션 초기화"
        onClick={() => run("reset")}
      >
        <RotateCcw size={17} />
      </button>
      <button
        className="primary"
        onClick={() =>
          run(state.running ? "pause" : state.finished ? "next" : "start")
        }
      >
        {state.running ? (
          <Pause size={18} />
        ) : state.finished ? (
          <SkipForward size={18} />
        ) : (
          <Play size={18} />
        )}{" "}
        {state.running
          ? "일시정지"
          : state.finished
            ? "다음 세션"
            : state.elapsed
              ? "계속"
              : "시작"}
      </button>
      {state.mode === "pomodoro" && (
        <button
          className="icon-button"
          title="다음 세션"
          aria-label="다음 세션"
          onClick={() => run("next")}
        >
          <SkipForward size={18} />
        </button>
      )}
    </div>
  );
}
function FocusCommentSettings({ comments, onClose }: { comments: FocusComments; onClose: () => void }) {
  const { notify } = useCalix();
  const [draft, setDraft] = useState({ ...comments });
  const [pending, setPending] = useState(false);
  return <Modal title="집중 문구" onClose={onClose}>
    <form className="focus-comment-form" onSubmit={event => {
      event.preventDefault();
      if (pending) return;
      setPending(true);
      void command("comments", { comments: draft }).then(() => { notify("저장됨"); onClose(); })
        .catch(error => notify(String(error))).finally(() => setPending(false));
    }}>
      {([['heading', '집중 문구'], ['focus_end', '집중 완료'], ['break_end', '휴식 완료']] as const).map(([key, title]) =>
        <label key={key}>{title}<input value={draft[key]} maxLength={key === 'heading' ? 80 : 120} onChange={event => setDraft(previous => ({ ...previous, [key]: event.target.value }))} /></label>)}
      <div className="dialog-actions">
        <button type="button" disabled={pending} onClick={() => setDraft({ ...DEFAULT_FOCUS_COMMENTS })}>기본값</button>
        <button type="button" onClick={onClose}>취소</button>
        <button type="submit" className="primary" disabled={pending}>저장</button>
      </div>
    </form>
  </Modal>;
}
export function FocusDock() {
  const state = useFocus(),
    [tick, setTick] = useState(0),
    [collapsed, setCollapsed] = useState(false);
  const { notify } = useCalix();
  useEffect(() => {
    let alive = true;
    void read().catch(() => {});
    const off = subscribe((e) => {
      if (e.event === "data-changed") void read().catch(() => {});
    });
    const t = setInterval(() => {
      if (alive && current?.running) void read().catch(() => {});
    }, 10000);
    return () => {
      alive = false;
      off();
      clearInterval(t);
    };
  }, []);
  useEffect(() => {
    if (!state?.running) return;
    const t = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [state?.running]);
  const seconds = state ? focusSeconds(state, performance.now() - readAt) : 0;
  useEffect(() => {
    if (state?.running && state.mode !== "free" && seconds === 0) {
      void read()
        .catch(() => {});
    }
  }, [seconds, state?.running]);
  useEffect(() => {
    if (!state?.finished || state.mode === "free") return;
    const session = `${state.session_id ?? ''}:${state.phase}:${state.round}`;
    if (notifiedSession === session) return;
    notifiedSession = session;
    const comments = state.comments ?? DEFAULT_FOCUS_COMMENTS;
    const message = state.phase === "focus" ? comments.focus_end : comments.break_end;
    if (message) notify(message);
  }, [state?.finished, state?.session_id, state?.phase, state?.round, state?.comments]);
  void tick;
  if (!state || (!state.running && !state.elapsed && !state.round)) return null;
  return (
    <aside
      className={`focus-dock glass ${collapsed ? "collapsed" : ""}`}
      aria-label="집중 타이머"
    >
      <button
        className="icon-button focus-collapse"
        aria-label={collapsed ? "타이머 펼치기" : "타이머 접기"}
        onClick={() => setCollapsed(!collapsed)}
      >
        {collapsed ? <Timer size={18} /> : <X size={15} />}
      </button>
      {!collapsed && (
        <>
          <div className="focus-brand">
            <img src="/assets/icons/calix.svg" alt="Calix" />
            <span>
              {state.phase === "break"
                ? "휴식"
                : state.mode === "free"
                  ? "자유 집중"
                  : "POMODORO"}
            </span>
          </div>
          <div className="dock-clock">
            <Tomato />
            <strong>{timerText(seconds)}</strong>
          </div>
          <Controls state={state} />
        </>
      )}
    </aside>
  );
}
export function weeklyMetrics(events: EventItem[], start: string, end: string) {
  const rows = events.filter(
    (e) =>
      !e.manual &&
      e.due_at &&
      dateKey(e.due_at) >= start &&
      dateKey(e.due_at) <= end,
  );
  const ratio = (kind: string) => {
    const all = rows.filter((e) => e.kind === kind),
      done = all.filter((e) => e.completed && e.completion_verified).length;
    return {
      total: all.length,
      done,
      percent: all.length ? Math.round((done / all.length) * 100) : null,
    };
  };
  return {
    videos: ratio("movie"),
    assignments: ratio("assignment"),
    pending: rows.filter((e) => !e.completed || !e.completion_verified).length,
  };
}
export function StudyPage() {
  const { data, notify } = useCalix(),
    state = useFocus();
  const [mode, setMode] = useState("pomodoro"),
    [work, setWork] = useState(25),
    [short, setShort] = useState(5),
    [long, setLong] = useState(15),
    [totals, setTotals] = useState<{ day: string; seconds: number }[]>([]),
    [offset, setOffset] = useState(0);
  const [commentSettings, setCommentSettings] = useState(false);
  const comments = state?.comments ?? DEFAULT_FOCUS_COMMENTS;
  useEffect(() => {
    if (state) {
      setMode(state.mode);
      setWork(state.work);
      setShort(state.short);
      setLong(state.long);
    }
  }, [state?.mode, state?.work, state?.short, state?.long]);
  useEffect(() => {
    let alive = true;
    const load = () =>
      void rpc<{ day: string; seconds: number }[]>("focus.totals")
        .then((v) => {
          if (alive) setTotals(v);
        })
        .catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  // Use KST date arithmetic rather than the host time zone.
  const kst = new Date(new Date(`${dateKey()}T00:00:00Z`).getTime());
  kst.setUTCDate(kst.getUTCDate() - ((kst.getUTCDay() + 6) % 7) + offset * 7);
  const days = Array.from({ length: 7 }, (_, i) =>
    new Date(kst.getTime() + i * 86400000).toISOString().slice(0, 10),
  );
  const metrics = weeklyMetrics(data.events, days[0], days[6]),
    seconds = totals
      .filter((t) => days.includes(t.day))
      .reduce((a, b) => a + b.seconds, 0),
    max = Math.max(
      60,
      ...days.map((d) => totals.find((t) => t.day === d)?.seconds || 0),
    );
  return (
    <section className="learning-page study-page">
      <div className="section-heading">
        <div>
          <p className="eyebrow">MAKE TIME</p>
          <h1>나의 학습</h1>
        </div>
        <div>
          <button onClick={() => setOffset(offset - 1)} aria-label="이전 주">
            ←
          </button>
          <span className="week-range">
            {days[0]} — {days[6]}
          </span>
          <button
            onClick={() => setOffset(offset + 1)}
            disabled={offset >= 0}
            aria-label="다음 주"
          >
            →
          </button>
        </div>
      </div>
      <div className="study-metrics">
        {[
          ["영상 수강", metrics.videos],
          ["과제 제출", metrics.assignments],
        ].map(([title, value]) => {
          const v = value as typeof metrics.videos;
          return (
            <article className="glass" key={String(title)}>
              <span>{String(title)}</span>
              <strong>{v.percent === null ? "—" : `${v.percent}%`}</strong>
              <progress max={100} value={v.percent ?? 0} />
              <small>
                {v.done} / {v.total}건
              </small>
            </article>
          );
        })}
        <article className="glass">
          <span>미완료 항목</span>
          <strong>
            {metrics.pending}
            <small>건</small>
          </strong>
          <small>이번 주 마감 기준</small>
        </article>
        <article className="glass">
          <span>집중 시간</span>
          <strong>
            {Math.floor(seconds / 60)}
            <small>분</small>
          </strong>
        </article>
      </div>
      <div className="study-columns">
        <section className="glass focus-card">
          <div className="focus-brand">
            <img src="/assets/icons/calix.svg" alt="Calix" />
            <span>FOCUS</span>
            <button className="icon-button focus-settings" type="button" title="집중 문구 설정" aria-label="집중 문구 설정" disabled={!state} onClick={() => setCommentSettings(true)}><Settings size={18} /></button>
          </div>
          <Tomato />
          {comments.heading && <h2>{comments.heading}</h2>}
          <div className="segmented">
            <button
              aria-pressed={mode === "pomodoro"}
              disabled={!!state?.elapsed || state?.running}
              onClick={() => setMode("pomodoro")}
            >
              뽀모도로
            </button>
            <button
              aria-pressed={mode === "free"}
              disabled={!!state?.elapsed || state?.running}
              onClick={() => setMode("free")}
            >
              자유 집중
            </button>
          </div>
          <div className="focus-options">
            {(
              [
                ["집중", work, setWork],
                ["짧은 휴식", short, setShort],
                ["긴 휴식", long, setLong],
              ] as const
            ).map(([label, value, set]) => (
              <label key={label}>
                {label}
                <NumberField
                  aria-label={`${label} 분`}

                  min={1}
                  max={180}
                  value={value}
                  disabled={
                    mode === "free" || !!state?.elapsed || state?.running
                  }
                  onValueChange={set}
                />
                분
              </label>
            ))}
          </div>
          {mode === "pomodoro" && !!state?.round && (
            <p className="muted">
              {(state.round % 4) + 1} / 4 세션
            </p>
          )}
          {(!state || (!state.running && !state.elapsed && !state.round)) && (
            <button
              className="primary"
              disabled={state?.running || !!state?.elapsed}
              onClick={() =>
                void command("configure", { mode, work, short, long })
                  .then(() => command("start"))
                  .catch((e) => notify(String(e)))
              }
            >
              <Play size={18} />
              집중 시작
            </button>
          )}
          {state && (state.running || state.elapsed > 0 || state.round > 0) && (
            <Controls state={state} />
          )}
        </section>
        <section className="glass focus-history">
          <h2>요일별 집중 시간</h2>
          <div className="focus-bars">
            {days.map((d, i) => {
              const s = totals.find((t) => t.day === d)?.seconds || 0;
              return (
                <div key={d}>
                  <small>{Math.floor(s / 60)}분</small>
                  <div className="focus-bar-track">
                    <span style={{ height: `${(s / max) * 100}%` }} />
                  </div>
                  <span>{["월", "화", "수", "목", "금", "토", "일"][i]}</span>
                </div>
              );
            })}
          </div>
        </section>
      </div>
      {commentSettings && <FocusCommentSettings comments={comments} onClose={() => setCommentSettings(false)} />}
    </section>
  );
}
