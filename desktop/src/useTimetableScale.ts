import { useLayoutEffect, useRef, useState } from "react";
export function useTimetableScale(
  start: number,
  end: number,
  ready = true,
  fixedUnit = 0,
) {
  const panel = useRef<HTMLElement>(null),
    [unit, setUnit] = useState(64);
  useLayoutEffect(() => {
    let frame = 0;
    const element = panel.current;
    if (!ready || !element) return;
    const measure = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const header = element.querySelector(".week-headers")?.clientHeight ?? 0;
        const available = element.clientHeight - header;
        const hours = Math.max(1, (end - start) / 60);
        const next = fixedUnit || Math.max(40, Math.min(64, available / hours));
        setUnit((previous) =>
          Math.abs(previous - next) > 0.2 ? next : previous,
        );
      });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    measure();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [start, end, ready, fixedUnit]);
  return { panel, unit, height: ((end - start) / 60) * unit };
}
