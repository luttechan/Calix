import { useLayoutEffect, useRef, useState } from "react";
export function useTimetableScale(start: number, end: number) {
  const panel = useRef<HTMLElement>(null),
    [unit, setUnit] = useState(64);
  useLayoutEffect(() => {
    let frame = 0;
    const measure = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!panel.current) return;
        const main = panel.current.closest("main");
        const bottom = main?.getBoundingClientRect().bottom || innerHeight;
        const available =
          bottom - panel.current.getBoundingClientRect().top - 80;
        const hours = Math.max(1, (end - start) / 60);
        const next = Math.max(32, Math.min(64, available / hours));
        setUnit((previous) =>
          Math.abs(previous - next) > 0.2 ? next : previous,
        );
      });
    };
    const observer = new ResizeObserver(measure);
    const main = panel.current?.closest("main");
    if (main) observer.observe(main);
    window.addEventListener("resize", measure);
    measure();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [start, end]);
  return { panel, unit, height: ((end - start) / 60) * unit };
}
