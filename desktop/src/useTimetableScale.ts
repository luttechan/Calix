import { useLayoutEffect, useRef, useState } from "react";
export function useTimetableScale(
  start: number,
  end: number,
  ready = true,
  fixedUnit = 0,
  hasOnline = false,
) {
  const panel = useRef<HTMLElement>(null);
  const [fitUnit, setFitUnit] = useState(64);
  useLayoutEffect(() => {
    const element = panel.current;
    if (!ready || !element || fixedUnit) return;
    const header = element.querySelector(".week-headers");
    const online = element.querySelector(".online-courses");
    const measure = () => {
      const available = element.clientHeight - (header?.clientHeight ?? 0) - (online?.clientHeight ?? 0);
      const next = Math.max(38, Math.min(64, available / 11));
      setFitUnit(previous => Math.abs(previous - next) > 0.2 ? next : previous);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (header) observer.observe(header);
    if (online) observer.observe(online);
    return () => observer.disconnect();
  }, [ready, fixedUnit, hasOnline]);
  const unit = fixedUnit || fitUnit;
  return { panel, unit, height: ((end - start) / 60) * unit };
}
