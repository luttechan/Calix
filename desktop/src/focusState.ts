export const DEFAULT_FOCUS_COMMENTS = { heading: "지금, 한 가지에 집중", focus_end: "집중을 마쳤습니다. 잠시 쉬세요.", break_end: "휴식을 마쳤습니다." };
export type FocusComments = typeof DEFAULT_FOCUS_COMMENTS;
export type FocusState = {
  comments?: FocusComments;
  session_id?: string;
  running: boolean;
  mode: "pomodoro" | "free";
  phase: "focus" | "break";
  round: number;
  elapsed: number;
  duration: number;
  work: number;
  short: number;
  long: number;
  finished: boolean;
};
export function focusSeconds(state: FocusState, elapsedSinceRead: number) {
  const elapsed =
    state.elapsed +
    (state.running ? Math.max(0, Math.floor(elapsedSinceRead / 1000)) : 0);
  return state.mode === "free"
    ? elapsed
    : Math.max(0, state.duration - elapsed);
}
export function timerText(seconds: number) {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60)
    .toString()
    .padStart(2, "0")}:${(value % 60).toString().padStart(2, "0")}`;
}
