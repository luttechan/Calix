export type SyncNoticeState = {
  phase: "running" | "success" | "warning" | "error" | "cancelled";
  message: string;
  current: number;
  total: number;
  remainingSeconds: number | null;
  stats: Record<string, number>;
  warnings: string[];
};
const initial = (): SyncNoticeState => ({
  phase: "running",
  message: "학교 일정 확인 중",
  current: 0,
  total: 0,
  remainingSeconds: null,
  stats: {},
  warnings: [],
});
export function syncNoticeState(
  state: SyncNoticeState | null,
  event: Record<string, unknown>,
): SyncNoticeState | null {
  if (event.event === "sync-started") return initial();
  if (event.event === "sync-progress") {
    if (state && state.phase !== "running") return state;
    const next = {
      ...(state || initial()),
      message: String(event.message || "학교 일정 확인 중").slice(0, 300),
    };
    if (Number.isSafeInteger(event.total) && Number(event.total) > 0) {
      next.remainingSeconds = Number.isSafeInteger(event.remainingSeconds)
        && Number(event.remainingSeconds) > 0
        ? Number(event.remainingSeconds)
        : null;
      next.total = Number(event.total);
      next.current = Math.max(
        0,
        Math.min(next.total, Number(event.current) || 0),
      );
    }
    return next;
  }
  if (event.event === "sync-complete") {
    const warnings = Array.isArray(event.warnings)
      ? event.warnings
          .filter((v): v is string => typeof v === "string")
          .slice(0, 100)
      : [];
    const stats: Record<string, number> = {};
    if (event.stats && typeof event.stats === "object")
      for (const [key, value] of Object.entries(event.stats))
        if (Number.isSafeInteger(value) && Number(value) >= 0)
          stats[key] = Number(value);
    return {
      ...(state || initial()),
      phase: warnings.length ? "warning" : "success",
      message: String(event.message || "동기화 완료"),
      warnings,
      stats,
    };
  }
  if (event.event === "sync-error")
    return {
      ...(state || initial()),
      phase: "error",
      message: String(
        event.message || "학교 일정을 확인하지 못했습니다.",
      ).slice(0, 300),
    };
  if (event.event === "sync-cancelled")
    return {
      ...(state || initial()),
      phase: "cancelled",
      message: "동기화를 중단했습니다.",
    };
  return state;
}
