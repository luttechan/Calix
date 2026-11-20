import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

const storageKey = "calix.checklist.columns";
const minimums = [152, 122, 94, 88, 94, 100, 100];
const maximum = 760;
const actionWidth = 46;

function loadWidths() {
  try {
    const values: unknown = JSON.parse(localStorage.getItem(storageKey) ?? "null");
    if (Array.isArray(values) && values.length === minimums.length && values.every((width, index) => Number.isInteger(width) && width >= minimums[index] && width <= maximum)) return values as number[];
  } catch { /* Keep the default layout when storage is unavailable. */ }
  return null;
}

function saveWidths(widths: number[] | null) {
  try {
    if (widths) localStorage.setItem(storageKey, JSON.stringify(widths));
    else localStorage.removeItem(storageKey);
  } catch { /* Resizing remains available for this session. */ }
}

function measure(handle: HTMLElement) {
  return Array.from(handle.closest("tr")?.cells ?? []).slice(0, minimums.length)
    .map((cell, index) => clamp(index, cell.getBoundingClientRect().width));
}

const clamp = (index: number, width: number) => Math.max(minimums[index], Math.min(maximum, Math.round(width)));

export function useChecklistWidths() {
  const [widths, setWidths] = useState<number[] | null>(loadWidths);
  const drag = useRef<{ x: number; values: number[]; latest: number[] } | null>(null);
  const resize = (values: number[], index: number, step: number) => values.map((width, column) => column === index ? clamp(column, width + step) : width);
  const end = () => {
    if (!drag.current) return;
    saveWidths(drag.current.latest);
    drag.current = null;
  };
  return {
    widths,
    actionWidth,
    tableWidth: widths ? widths.reduce((sum, value) => sum + value, actionWidth) : undefined,
    handle: (index: number, title: string) => ({
      role: "separator",
      tabIndex: 0,
      "aria-label": `${title} 열 너비`,
      "aria-orientation": "vertical" as const,
      "aria-valuemin": minimums[index],
      "aria-valuemax": maximum,
      "aria-valuenow": widths?.[index] ?? minimums[index],
      title: `${title} 열 너비 조절`,
      onPointerDown(event: PointerEvent<HTMLSpanElement>) {
        if (event.button !== 0) return;
        const values = widths ?? measure(event.currentTarget);
        drag.current = { x: event.clientX, values, latest: values };
        event.currentTarget.setPointerCapture(event.pointerId);
      },
      onPointerMove(event: PointerEvent<HTMLSpanElement>) {
        if (!drag.current || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
        const next = resize(drag.current.values, index, event.clientX - drag.current.x);
        drag.current.latest = next;
        setWidths(next);
      },
      onPointerUp: end,
      onPointerCancel: end,
      onLostPointerCapture: end,
      onDoubleClick() { setWidths(null); saveWidths(null); },
      onKeyDown(event: KeyboardEvent<HTMLSpanElement>) {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const next = resize(widths ?? measure(event.currentTarget), index, event.key === "ArrowLeft" ? -12 : 12);
        setWidths(next);
        saveWidths(next);
      },
    }),
  };
}
